"""Central logging configuration.

Writes to both the console and a rotating file at ``logs/app.log``.
Use ``get_logger(__name__)`` anywhere in the app.
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config.settings import settings

_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_configured = False


def _configure_root() -> None:
    global _configured
    if _configured:
        return

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    file_handler = RotatingFileHandler(
        _LOG_DIR / "app.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    root = logging.getLogger("permit_agent")
    root.setLevel(settings.LOG_LEVEL)
    root.addHandler(console)
    root.addHandler(file_handler)
    root.propagate = False

    _configured = True


def get_logger(name: str = "permit_agent") -> logging.Logger:
    """Return a namespaced logger under the ``permit_agent`` root."""
    _configure_root()
    if name == "permit_agent":
        return logging.getLogger("permit_agent")
    return logging.getLogger(f"permit_agent.{name}")
