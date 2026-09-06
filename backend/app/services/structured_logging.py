# backend/app/services/structured_logging.py
"""Small JSON logger configuration for Cloud Run and Agent Engine telemetry."""

import json
import logging
import sys
from typing import Any


# Emit one compact JSON object so Google Cloud stores queryable structured fields.
class CloudJsonFormatter(logging.Formatter):
    """Format metadata dictionaries without serializing request or response bodies."""

    def format(self, record: logging.LogRecord) -> str:
        """Return a stable structured log line for Cloud Logging ingestion."""

        try:
            payload = dict(record.msg) if isinstance(record.msg, dict) else {"event": str(record.msg)}
            payload.setdefault("severity", record.levelname)
            payload.setdefault("logger", record.name)
            return json.dumps(payload, default=str, separators=(",", ":"))
        except (TypeError, ValueError):
            return json.dumps({"event": "logging_format_error", "severity": "ERROR"})


# Give each application logger one non-propagating JSON stream handler.
def configure_structured_logger(name: str) -> logging.Logger:
    """Return a logger that emits metadata-only JSON to standard output."""

    logger = logging.getLogger(name)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(CloudJsonFormatter())
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


# Keep event call sites concise and prevent accidental arbitrary object logging.
def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Write one named event with explicitly selected safe scalar metadata."""

    logger.info({"event": event, **fields})
