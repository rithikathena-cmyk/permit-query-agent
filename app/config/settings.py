"""Application settings loaded from the environment (.env)."""
import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Central configuration read from environment variables."""

    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "permits")

    # --- Query safety / observability ---
    # Abort any query running longer than this (milliseconds).
    QUERY_TIMEOUT_MS: int = int(os.getenv("QUERY_TIMEOUT_MS", "5000"))
    # Log a warning for queries slower than this (milliseconds).
    SLOW_QUERY_MS: int = int(os.getenv("SLOW_QUERY_MS", "1000"))
    # Max rows a single read query may return (defense against huge scans).
    MAX_ROWS: int = int(os.getenv("MAX_ROWS", "1000"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def database_url(self) -> str:
        """SQLAlchemy connection URL for MySQL via PyMySQL."""
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )


settings = Settings()
