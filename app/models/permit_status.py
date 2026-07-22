from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class PermitStatus(Base):
    __tablename__ = "permit_statuses"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(30), unique=True)

    permits = relationship("Permit", back_populates="status")
