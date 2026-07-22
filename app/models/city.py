from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(primary_key=True)
    city_name: Mapped[str] = mapped_column(String(100))
    county: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100))

    permits = relationship("Permit", back_populates="city")
