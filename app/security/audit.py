"""Audit-history writer.

Persists one ``query_audit`` row per query attempt. Uses its own database
session so the audit record survives even when the queried session errored
or was rolled back.
"""
from app.database.connection import SessionLocal
from app.logging.logger import get_logger
from app.models.query_audit import QueryAudit

logger = get_logger("audit")


class AuditLog:
    def record(
        self,
        query_text: str,
        success: bool,
        duration_ms: float,
        row_count: int | None = None,
        error: str | None = None,
    ) -> None:
        db = SessionLocal()
        try:
            db.add(
                QueryAudit(
                    query_text=query_text,
                    success=success,
                    duration_ms=round(duration_ms, 2),
                    row_count=row_count,
                    error=(error[:2000] if error else None),
                )
            )
            db.commit()
        except Exception as exc:  # never let auditing break the request
            db.rollback()
            logger.error("Failed to write audit record: %s", exc)
        finally:
            db.close()
