"""Unit tests for the SchemaService (introspection is mocked — no database)."""
from unittest.mock import MagicMock, patch

from app.security.constants import ALLOWED_TABLES
from app.services.schema_service import SchemaService


def _fake_inspector():
    """An inspector exposing a mix of allowed, disallowed, and view tables."""
    inspector = MagicMock()
    # `secret` is NOT allowlisted; `permit_details` is an allowlisted view.
    inspector.get_table_names.return_value = [
        "permits",
        "permit_statuses",
        "secret",
    ]
    inspector.get_view_names.return_value = ["permit_details"]

    def get_columns(table):
        cols = {
            "permits": [
                {"name": "id", "type": "INTEGER"},
                {"name": "status_id", "type": "INTEGER"},
            ],
            "permit_statuses": [
                {"name": "id", "type": "INTEGER"},
                {"name": "status", "type": "VARCHAR(30)"},
            ],
            "permit_details": [{"name": "status", "type": "VARCHAR(30)"}],
        }
        return cols.get(table, [])

    def get_foreign_keys(table):
        if table == "permits":
            return [
                {
                    "constrained_columns": ["status_id"],
                    "referred_table": "permit_statuses",
                    "referred_columns": ["id"],
                }
            ]
        return []

    inspector.get_columns.side_effect = get_columns
    inspector.get_foreign_keys.side_effect = get_foreign_keys
    return inspector


def _service_with(inspector):
    db = MagicMock()
    with patch(
        "app.services.schema_service.inspect", return_value=inspector
    ):
        return SchemaService(db).get_schema()


def test_only_allowlisted_tables_are_returned():
    schema = _service_with(_fake_inspector())
    assert "secret" not in schema  # present in DB but not allowlisted
    assert "permits" in schema
    assert "permit_statuses" in schema


def test_allowlisted_view_is_included():
    schema = _service_with(_fake_inspector())
    assert "permit_details" in schema  # a view, still surfaced


def test_allowlisted_but_absent_table_is_omitted():
    schema = _service_with(_fake_inspector())
    # `cities`/`officers` are allowlisted but not present in this fake DB.
    for absent in ALLOWED_TABLES - {"permits", "permit_statuses", "permit_details"}:
        assert absent not in schema


def test_columns_and_foreign_keys_are_reported():
    schema = _service_with(_fake_inspector())
    assert {"name": "id", "type": "INTEGER"} in schema["permits"]["columns"]
    assert schema["permits"]["foreign_keys"] == [
        {"column": "status_id", "references": "permit_statuses.id"}
    ]
    assert schema["permit_statuses"]["foreign_keys"] == []
