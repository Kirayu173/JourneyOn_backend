from __future__ import annotations

import logging
from logging.config import dictConfig
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler
from pathlib import Path

from app.core.config import settings
from app.core.request_context import request_id_var


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        # attach request_id if available
        rid = request_id_var.get()
        setattr(record, "request_id", rid or "-")
        return True


def setup_logging(level: str = "info") -> None:
    """Configure structured logging with optional file rotation and request correlation."""
    level_upper = level.upper()

    # Ensure log directory exists if writing to file
    handlers: dict[str, dict] = {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["reqid"],
        }
    }

    if settings.LOG_TO_FILE:
        Path(settings.LOG_FILE_PATH).parent.mkdir(parents=True, exist_ok=True)
        if settings.LOG_ROTATION_POLICY == "time":
            handlers["file"] = {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "formatter": "json",
                "filters": ["reqid"],
                "filename": settings.LOG_FILE_PATH,
                "when": settings.LOG_ROTATION_WHEN,
                "interval": settings.LOG_ROTATION_INTERVAL,
                "backupCount": settings.LOG_BACKUP_COUNT,
                "encoding": "utf-8",
            }
        else:
            handlers["file"] = {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "filters": ["reqid"],
                "filename": settings.LOG_FILE_PATH,
                "maxBytes": settings.LOG_MAX_BYTES,
                "backupCount": settings.LOG_BACKUP_COUNT,
                "encoding": "utf-8",
            }

    dictConfig(
        {
            "version": 1,
            "filters": {
                "reqid": {
                    "()": RequestIdFilter,
                }
            },
            "formatters": {
                "json": {
                    "format": (
                        "{\"ts\":%(asctime)s, \"lvl\":%(levelname)s, "
                        "\"logger\":%(name)s, \"msg\":%(message)s, "
                        "\"req_id\":%(request_id)s}"
                    )
                }
            },
            "handlers": handlers,
            "root": {
                "level": level_upper,
                "handlers": list(handlers.keys()),
            },
        }
    )
    logging.getLogger(__name__).info("Logging configured", extra={"level": level_upper})