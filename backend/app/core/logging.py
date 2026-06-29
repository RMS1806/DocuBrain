"""
Structured JSON logging + per-request correlation ID.

ContextVar: Python's async-safe equivalent of a thread-local.
Any coroutine running inside a request's async context reads the same
correlation_id value set by CorrelationIDMiddleware at request entry.
"""

import json
import logging
import time
from contextvars import ContextVar

# The ContextVar holds the correlation ID for the current async context.
# Default is "-" so log lines emitted outside a request are still valid JSON.
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


class JSONFormatter(logging.Formatter):
    """Emit every log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "correlation_id": correlation_id.get(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    """
    Replace the root handler with a JSON-emitting StreamHandler.
    Call once at application startup before any loggers are used.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
