"""Schema service — introspects the live database for the MCP schema tool.

Flow:  Claude -> get_database_schema() -> SchemaService -> SQLAlchemy inspect()

Why this exists
---------------
Without schema awareness the model *guesses* table and column names (e.g. it
invents ``statuses`` when the real table is ``permit_statuses``). Exposing the
real schema lets Claude generate correct SQL and join lookup tables instead of
returning raw foreign-key ids.

Design notes
------------
* The schema is reflected **dynamically** with ``inspect()`` so it stays in
  sync with the database — no hardcoded column lists to drift.
* It is intersected with :data:`ALLOWED_TABLES`, so the tool never advertises a
  table the SQL Guard would reject. What Claude can *see* here is exactly what
  it can *query*.
* Both base tables and views are considered (``permit_details`` is a view).
"""
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.logging.logger import get_logger
from app.security.constants import ALLOWED_TABLES

logger = get_logger("schema_service")


class SchemaService:
    """Return the accessible portion of the database schema."""

    def __init__(self, db: Session):
        self.db = db

    def get_schema(self) -> dict:
        """Reflect columns and foreign keys for every allowed, existing table.

        Returns
        -------
        dict
            ``{table_name: {"columns": [...], "foreign_keys": [...]}}`` for
            every table that is both in ``ALLOWED_TABLES`` and present in the
            database (base tables and views).
        """
        inspector = inspect(self.db.get_bind())

        # Only surface tables that are BOTH allowlisted AND actually present.
        existing = set(inspector.get_table_names()) | set(
            inspector.get_view_names()
        )
        visible = sorted(ALLOWED_TABLES & existing)

        schema: dict = {}
        for table in visible:
            columns = [
                {"name": col["name"], "type": str(col["type"])}
                for col in inspector.get_columns(table)
            ]

            foreign_keys = [
                {
                    "column": fk["constrained_columns"][0],
                    "references": (
                        f"{fk['referred_table']}."
                        f"{fk['referred_columns'][0]}"
                    ),
                }
                for fk in inspector.get_foreign_keys(table)
                if fk.get("constrained_columns")
                and fk.get("referred_columns")
            ]

            schema[table] = {
                "columns": columns,
                "foreign_keys": foreign_keys,
            }

        logger.info("Schema introspected: tables=%d", len(schema))
        return schema
