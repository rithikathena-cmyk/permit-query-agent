"""Database engine/session setup.

Configuration is read from the environment (``.env``) so the connection
details never live in code. The individual ``DB_HOST`` / ``DB_PORT`` /
``DB_NAME`` / ``DB_USER`` / ``DB_PASSWORD`` variables are assembled into a
SQLAlchemy URL, each with a sane default so the URL is always valid (no
``None:None`` parse crashes when nothing is set).

Two supported targets:
  * Local MySQL   — ``DB_HOST=localhost``, ``DB_PORT=3306``, ``DB_SSL`` unset
    (plaintext connection).
  * Aiven for MySQL — the service host, its assigned port, and ``DB_SSL=true``.
    Aiven requires TLS and ships its own CA; point ``DB_SSL_CA`` at the
    downloaded ``ca.pem`` so the server certificate is verified.

``create_engine`` only parses the URL and sets up the pool; it does not open a
connection, so importing this module never fails just because the database is
unreachable — that surfaces later, at query time, where it can be handled.
"""
import os
import ssl
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load .env from the project root explicitly, not from the current working
# directory. ``load_dotenv()`` with no argument searches upward from the cwd, so
# launching Streamlit (or anything else) from a different directory would leave
# DB_* unset and the connection would silently fall back to bad defaults
# ("Access denied ... using password: NO"). Anchoring to this file's location
# makes config load regardless of where the process is started.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _database_url() -> str:
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME", "permit_system")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    return (
        f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}"
        "?charset=utf8mb4"
    )


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def _connect_args() -> dict:
    """TLS options for pymysql, enabled via ``DB_SSL`` for Aiven for MySQL.

    Local development (``DB_SSL`` unset) connects without TLS, unchanged. Aiven
    requires an encrypted connection, so set ``DB_SSL=true`` there. Aiven ships
    its own CA certificate: download ``ca.pem`` from the service overview and
    point ``DB_SSL_CA`` at it so the server certificate is verified. Without a
    CA file the connection is still encrypted but the certificate is not
    verified (fine for a quick test, not for production).
    """
    if not _truthy(os.getenv("DB_SSL")):
        return {}
    ca = os.getenv("DB_SSL_CA")
    if ca:
        context = ssl.create_default_context(cafile=ca)
    else:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return {"ssl": context}


DATABASE_URL = _database_url()

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args=_connect_args(),
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def admin_engine():
    """Engine using elevated (write/DDL) credentials for setup scripts.

    The application and MCP server connect through ``engine`` as the
    least-privilege read-only user (``DB_USER``). Schema creation, seeding, and
    user management need write/DDL rights, so those scripts build a separate
    engine from ``DB_ADMIN_USER`` / ``DB_ADMIN_PASSWORD`` (falling back to the
    app credentials when no admin override is configured). On Aiven the admin
    user is ``avnadmin``.
    """
    user = os.getenv("DB_ADMIN_USER") or os.getenv("DB_USER", "root")
    password = os.getenv("DB_ADMIN_PASSWORD") or os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME", "permit_system")
    url = (
        f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}"
        "?charset=utf8mb4"
    )
    return create_engine(
        url, pool_pre_ping=True, connect_args=_connect_args()
    )
