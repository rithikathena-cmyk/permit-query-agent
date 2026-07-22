"""Unit tests for the SQL Guard (pure, no database needed)."""
import pytest

from app.security.exceptions import SQLValidationError
from app.security.sql_guard import SQLGuard


# ---------------------------------------------------------------------------
# Queries that should PASS
# ---------------------------------------------------------------------------
def test_simple_select_gets_limit_appended():
    out = SQLGuard.validate("SELECT * FROM permits")
    assert out == "SELECT * FROM permits LIMIT 100"


def test_existing_limit_is_preserved():
    out = SQLGuard.validate("SELECT * FROM permits LIMIT 5")
    assert out.endswith("LIMIT 5")
    assert out.count("LIMIT") == 1


def test_join_on_allowed_tables():
    sql = "SELECT * FROM permits p JOIN cities c ON p.city_id = c.id"
    out = SQLGuard.validate(sql)
    assert "LIMIT 100" in out


def test_permit_details_view_allowed():
    out = SQLGuard.validate("SELECT status FROM permit_details")
    assert "LIMIT 100" in out


# ---------------------------------------------------------------------------
# Queries that should be BLOCKED
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM permits",
        "UPDATE permits SET applicant_name = 'x'",
        "DROP TABLE permits",
        "SHOW TABLES",
        "DESCRIBE permits",
    ],
)
def test_non_select_blocked(sql):
    with pytest.raises(SQLValidationError):
        SQLGuard.validate(sql)


def test_stacked_statements_blocked():
    with pytest.raises(SQLValidationError, match="Multiple"):
        SQLGuard.validate("SELECT 1; DROP TABLE permits")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM permits -- comment",
        "SELECT * FROM permits /* comment */",
    ],
)
def test_comments_blocked(sql):
    with pytest.raises(SQLValidationError, match="Comments"):
        SQLGuard.validate(sql)


def test_disallowed_table_blocked():
    with pytest.raises(SQLValidationError, match="query_audit"):
        SQLGuard.validate("SELECT * FROM query_audit")


def test_subquery_disallowed_table_blocked():
    sql = "SELECT * FROM permits WHERE id IN (SELECT id FROM secret)"
    with pytest.raises(SQLValidationError, match="secret"):
        SQLGuard.validate(sql)


def test_comma_join_disallowed_table_blocked():
    # The classic gap: a second table introduced by a comma, not FROM/JOIN.
    sql = "SELECT * FROM permits, information_schema.tables"
    with pytest.raises(SQLValidationError):
        SQLGuard.validate(sql)


def test_comma_join_allowed_tables_pass():
    sql = "SELECT * FROM permits p, officers o WHERE p.officer_id = o.id"
    out = SQLGuard.validate(sql)
    assert "LIMIT 100" in out


def test_schema_qualified_table_blocked():
    with pytest.raises(SQLValidationError, match="Cross-schema"):
        SQLGuard.validate("SELECT * FROM mysql.user")


def test_backtick_cross_schema_blocked():
    with pytest.raises(SQLValidationError):
        SQLGuard.validate("SELECT * FROM `permits`, `mysql`.`user`")


def test_from_subselect_allowed():
    sql = "SELECT x FROM (SELECT id AS x FROM permits) sub"
    out = SQLGuard.validate(sql)
    assert "LIMIT 100" in out


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM permits INTO OUTFILE '/tmp/x'",
        "SELECT LOAD_FILE('/etc/passwd')",
    ],
)
def test_file_io_blocked(sql):
    with pytest.raises(SQLValidationError):
        SQLGuard.validate(sql)


def test_empty_sql_blocked():
    with pytest.raises(SQLValidationError, match="empty"):
        SQLGuard.validate("")
