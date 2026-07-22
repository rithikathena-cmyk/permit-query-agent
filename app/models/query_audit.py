from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class QueryAudit(Base):
    """One row per query attempt — the audit history trail."""

    __tablename__ = "query_audit"

    id: Mapped[int] = mapped_column(primary_key=True)
    query_text: Mapped[str] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(Boolean)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
