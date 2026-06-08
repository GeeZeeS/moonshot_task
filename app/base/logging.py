from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

LOGGER_NAME = "proxy"
SENSITIVE_HEADERS = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
}


def configure_logging() -> logging.Logger:
    _logger = logging.getLogger(LOGGER_NAME)
    if _logger.handlers:
        return _logger

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False
    return _logger


logger = configure_logging()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for key, value in headers.items():
        sanitized[key] = "***" if key.lower() in SENSITIVE_HEADERS else value
    return sanitized


def truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}...<truncated>"


def log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, "timestamp": utc_timestamp(), **fields}
    logger.info(json.dumps(payload, default=str, ensure_ascii=True))
