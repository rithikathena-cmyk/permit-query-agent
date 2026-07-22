from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class PermitDocument(Base):
    """A document requirement attached to a permit.

    ``received`` distinguishes documents already on file (True) from those the
    applicant still needs to supply (False). "Pending documents" are simply the
    rows where ``received`` is False.
    """

    __tablename__ = "permit_documents"

    id: Mapped[int] = mapped_column(primary_key=True)

    permit_id: Mapped[int] = mapped_column(
        ForeignKey("permits.id"), index=True
    )

    doc_name: Mapped[str] = mapped_column(String(120))

    received: Mapped[bool] = mapped_column(Boolean, default=False)

    permit = relationship("Permit", back_populates="documents")
