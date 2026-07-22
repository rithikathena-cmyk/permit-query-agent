"""Database engine/session setup.

Configuration is read from the environment so the same code runs locally
(from ``.env``) and on a host like Streamlit Cloud (where the UI bridges
``st.secrets`` into the environment before this module is imported).

Two ways to configure, in priority order:
  1. ``DATABASE_URL`` — a full SQLAlchemy URL (easiest for hosted MySQL).
  2. ``DB_HOST`` / ``DB_PORT`` / ``DB_NAME`` / ``DB_USER`` / ``DB_PASSWORD`` —
     assembled into a URL, each with a sane default so the URL is always
     valid (no more ``None:None`` parse crashes when nothing is set).

``create_engine`` only parses the URL and sets up the pool; it does not open a
connection, so importing this module never fails just because the database is
unreachable — that surfaces later, at query time, where it can be handled.
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME", "permits")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}"


DATABASE_URL = _database_url()

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)
