# src/log_utils.py
"""Structured logging utilities for the intercom-bridge project.

Usage:
    from src.log_utils import configure_logging
    configure_logging(json_output=True)   # call once in main()

    import logging
    logger = logging.getLogger(__name__)
    logger.info("Link created", extra={"src": "10", "dst": "43"})
"""

import json
import logging
from typing import Set

# Fields that are part of every LogRecord and should not be duplicated
# in the structured extra payload.
_STDLIB_FIELDS: Set[str] = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "taskName",
}


class JsonFormatter(logging.Formatter):
    """Emits one JSON object per log line for structured log ingestion.

    All fields added via ``extra={}`` are hoisted to the top-level JSON
    object alongside the standard ``ts``, ``level``, ``logger``, and ``msg``
    keys.
    """

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        payload: dict = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.message,
        }
        for key, value in record.__dict__.items():
            if key not in _STDLIB_FIELDS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO, json_output: bool = False) -> None:
    """Configure the root logger.

    Args:
        level:       Minimum log level (default: INFO).
        json_output: When True, each line is a JSON object (structured).
                     When False, uses a human-readable text format.
    """
    handler = logging.StreamHandler()
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        )
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)
