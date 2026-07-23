"""Database engine/session setup.

Configuration is read from the environment so the same code runs locally (from
``.env``) and on a host like Streamlit Cloud (where the UI bridges
``st.secrets`` into the environment before this module is imported).

Two ways to configure, in priority order:
  1. ``DATABASE_URL`` — a full SQLAlchemy URL (easiest for a hosted service;
     paste it straight from the provider). It is normalized: a bare
     ``mysql://`` scheme becomes ``mysql+pymysql://`` (SQLAlchemy would
     otherwise reach for the uninstalled ``MySQLdb`` driver), and a
     provider ``ssl-mode`` query param is stripped (TLS is applied via
     ``connect_args`` instead) while still switching TLS on.
  2. ``DB_HOST`` / ``DB_PORT`` / ``DB_NAME`` / ``DB_USER`` / ``DB_PASSWORD`` —
     assembled into a URL, each with a sane default so the URL is always
     valid (no ``None:None`` parse crashes when nothing is set).

Targets:
  * Local MySQL     — ``DB_HOST=localhost``, ``DB_PORT=3306``, ``DB_SSL`` unset.
  * Aiven for MySQL — the service host/port and ``DB_SSL=true`` (Aiven requires
    TLS). To verify the server cert, download ``ca.pem`` and set ``DB_SSL_CA``.

``create_engine`` only parses the URL and sets up the pool; it does not open a
connection, so importing this module never fails just because the database is
unreachable — that surfaces later, at query time, where it can be handled.
"""
import os
import ssl
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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


def _url_wants_tls(url: str | None) -> bool:
    """True if a DATABASE_URL asks for TLS via an ``ssl-mode`` param.

    Providers hand out URLs like ``...?ssl-mode=REQUIRED``. PyMySQL applies TLS
    through ``connect_args`` (not the URL), so we detect the intent here and
    turn TLS on even when ``DB_SSL`` was not set separately.
    """
    if not url:
        return False
    mode = dict(parse_qsl(urlsplit(url).query)).get("ssl-mode", "")
    return mode.upper() not in ("", "DISABLED", "PREFERRED")


def _normalize_url(url: str) -> str:
    """Make a provider-supplied URL safe for SQLAlchemy + PyMySQL.

    * ``mysql://`` -> ``mysql+pymysql://`` (a bare ``mysql://`` makes SQLAlchemy
      import ``MySQLdb``/mysqlclient, which we do not ship).
    * Drop the ``ssl-mode`` query param (a mysqlclient/libmysql option PyMySQL
      rejects); TLS is applied via ``connect_args`` instead.
    * Ensure ``charset=utf8mb4``.
    """
    parts = urlsplit(url)
    scheme = "mysql+pymysql" if parts.scheme == "mysql" else parts.scheme
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() != "ssl-mode"
    ]
    if not any(k == "charset" for k, _ in query):
        query.append(("charset", "utf8mb4"))
    return urlunsplit(
        (scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return _normalize_url(url)
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
    """TLS options for pymysql, for a hosted database like Aiven for MySQL.

    Local development (``DB_SSL`` unset, no ``ssl-mode`` in ``DATABASE_URL``)
    connects without TLS, unchanged. TLS turns on when ``DB_SSL=true`` OR the
    ``DATABASE_URL`` carries an ``ssl-mode`` that requires it. With ``DB_SSL_CA``
    set (path to the provider's ``ca.pem``) the server certificate is verified;
    otherwise the connection is encrypted but the certificate is not verified
    (matches Aiven's ``ssl-mode=REQUIRED``).
    """
    if not (_truthy(os.getenv("DB_SSL")) or _url_wants_tls(os.getenv("DATABASE_URL"))):
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
    # A hosted service (e.g. Streamlit Cloud) typically exposes a single
    # DATABASE_URL and no separate DB_* parts. When no explicit admin override
    # is given, reuse that URL so admin ops (init/seed) have a valid connection
    # rather than falling back to a broken localhost default.
    raw = os.getenv("DATABASE_URL")
    if raw and not os.getenv("DB_ADMIN_USER"):
        return create_engine(
            _normalize_url(raw), pool_pre_ping=True,
            connect_args=_connect_args(),
        )
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
