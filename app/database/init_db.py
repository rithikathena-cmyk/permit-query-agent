from app.database.base import Base
from app.database.connection import admin_engine

# Import all models here so SQLAlchemy registers them
import app.models  # noqa: F401

def create_database():
    # DDL needs write privileges — use the admin engine, not the read-only
    # app connection.
    Base.metadata.create_all(bind=admin_engine())
    print("Database tables created successfully.")


if __name__ == "__main__":
    create_database()
