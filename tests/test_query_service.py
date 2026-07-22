"""Integration tests for QueryService (requires the live MySQL database)."""
import pytest

from app.database.connection import SessionLocal
from app.security.exceptions import SQLValidationError
from app.services.query_service import QueryService


@pytest.fixture()
def service():
    db = SessionLocal()
    try:
        yield QueryService(db)
    finally:
        db.close()


def test_valid_query_returns_rows(service):
    rows = service.execute("SELECT id FROM permits LIMIT 3")
    assert isinstance(rows, list)
    assert len(rows) == 3
    assert "id" in rows[0]


def test_auto_limit_caps_results(service):
    # No LIMIT -> guard appends LIMIT 100
    rows = service.execute("SELECT id FROM permits")
    assert len(rows) == 100


def test_aggregate_query(service):
    rows = service.execute(
        "SELECT status_id, COUNT(*) AS c FROM permits GROUP BY status_id"
    )
    total = sum(r["c"] for r in rows)
    assert total == 1000


def test_blocked_query_raises(service):
    with pytest.raises(SQLValidationError):
        service.execute("DELETE FROM permits")


def test_blocked_table_raises(service):
    with pytest.raises(SQLValidationError):
        service.execute("SELECT * FROM query_audit")
