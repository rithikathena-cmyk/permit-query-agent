"""Query service — the single entry point the MCP server calls.

Flow:  Claude -> SQL -> SQLGuard -> QueryService -> Repository -> MySQL

Wraps read-only SQL execution with, in order:
  1. SQL Guard           (app.security.sql_guard.SQLGuard) -- the gatekeeper
  2. Query timeout       (MySQL MAX_EXECUTION_TIME)
  3. Performance timing   + slow-query detection
  4. Structured logging  (app.logging.logger)
  5. Audit history       (app.security.audit -> query_audit table)

The repository never validates SQL; the service always validates first.
The public ``execute(sql)`` signature is unchanged, so the MCP server does
not need any modification to gain these protections.
"""
import time

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.logging.logger import get_logger
from app.repositories.permit_repository import PermitRepository
from app.security.audit import AuditLog
from app.security.exceptions import SQLValidationError
from app.security.sql_guard import SQLGuard

logger = get_logger("query_service")


class QueryService:

    def __init__(self, db: Session):
        self.db = db
        self.repository = PermitRepository(db)
        self.audit = AuditLog()

    def execute(self, sql: str):
        start = time.perf_counter()
        logger.info("Query received: %s", sql)

        # 1. SQL Guard (gatekeeper) --------------------------------------
        try:
            validated_sql = SQLGuard.validate(sql)
        except SQLValidationError as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.warning("Query rejected (%s): %s", exc, sql)
            self.audit.record(
                query_text=sql,
                success=False,
                duration_ms=duration_ms,
                error=f"guard: {exc}",
            )
            raise

        # 2. Timeout + 3/4. execute with timing --------------------------
        try:
            # MAX_EXECUTION_TIME applies to read-only SELECTs (ms).
            self.db.execute(
                text(
                    f"SET SESSION MAX_EXECUTION_TIME = "
                    f"{int(settings.QUERY_TIMEOUT_MS)}"
                )
            )
            rows = self.repository.execute_read_query(validated_sql)
            duration_ms = (time.perf_counter() - start) * 1000

            logger.info(
                "Query OK: rows=%d duration=%.1fms", len(rows), duration_ms
            )
            if duration_ms >= settings.SLOW_QUERY_MS:
                logger.warning(
                    "SLOW QUERY (%.1fms >= %dms): %s",
                    duration_ms,
                    settings.SLOW_QUERY_MS,
                    validated_sql,
                )

            # 5. Audit ----------------------------------------------------
            self.audit.record(
                query_text=validated_sql,
                success=True,
                duration_ms=duration_ms,
                row_count=len(rows),
            )
            return rows

        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error("Query failed: %s | %s", validated_sql, exc)
            self.audit.record(
                query_text=validated_sql,
                success=False,
                duration_ms=duration_ms,
                error=str(exc),
            )
            raise
