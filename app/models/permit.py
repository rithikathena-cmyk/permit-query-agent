from datetime import date, datetime

from sqlalchemy import (
    String,
    Date,
    DateTime,
    Numeric,
    ForeignKey,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import Base


class Permit(Base):
    __tablename__ = "permits"

    id: Mapped[int] = mapped_column(primary_key=True)

    application_number: Mapped[str] = mapped_column(
        String(30),
        unique=True,
    )

    applicant_name: Mapped[str] = mapped_column(String(120))

    submitted_date: Mapped[date] = mapped_column(Date, index=True)

    approved_date: Mapped[date | None] = mapped_column(Date)

    # Projected date the review/inspection is expected to finish. Null for
    # permits with no meaningful estimate (e.g. Rejected).
    estimated_completion_date: Mapped[date | None] = mapped_column(Date)

    estimated_cost: Mapped[float] = mapped_column(
        Numeric(12, 2)
    )

    permit_type_id: Mapped[int] = mapped_column(
        ForeignKey("permit_types.id")
    )

    status_id: Mapped[int] = mapped_column(
        ForeignKey("permit_statuses.id")
    )

    city_id: Mapped[int] = mapped_column(
        ForeignKey("cities.id")
    )

    officer_id: Mapped[int] = mapped_column(
        ForeignKey("officers.id")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    permit_type = relationship(
        "PermitType",
        back_populates="permits",
    )

    status = relationship(
        "PermitStatus",
        back_populates="permits",
    )

    city = relationship(
        "City",
        back_populates="permits",
    )

    officer = relationship(
        "Officer",
        back_populates="permits",
    )

    documents = relationship(
        "PermitDocument",
        back_populates="permit",
        cascade="all, delete-orphan",
    )
