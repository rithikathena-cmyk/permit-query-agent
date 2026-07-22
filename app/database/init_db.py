from app.database.base import Base
from app.database.connection import engine

# Import all models here so SQLAlchemy registers them
import app.models  # noqa: F401

def create_database():
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")


if __name__ == "__main__":
    create_database()
