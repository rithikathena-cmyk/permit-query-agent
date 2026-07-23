"""Application settings loaded from the environment (.env).

Database connection config lives in ``app/database/connection.py`` (which reads
the ``DB_*`` / ``DB_SSL*`` variables directly). This module holds only the
query-safety and logging knobs used by the services.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Anchor .env loading to the project root so config loads no matter which
# directory the process (e.g. `streamlit run ui/app.py`) is started from.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class Settings:
    """Central configuration read from environment variables."""

    # --- Query safety / observability ---
    # Abort any query running longer than this (milliseconds).
    QUERY_TIMEOUT_MS: int = int(os.getenv("QUERY_TIMEOUT_MS", "5000"))
    # Log a warning for queries slower than this (milliseconds).
    SLOW_QUERY_MS: int = int(os.getenv("SLOW_QUERY_MS", "1000"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
