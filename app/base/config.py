from __future__ import annotations

import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    provider_name: str = os.getenv("SPORTS_PROVIDER")
    openliga_base_url: str = os.getenv("OPENLIGA_BASE_URL")
    upstream_timeout_seconds: float = os.getenv("UPSTREAM_TIMEOUT_SECONDS", 10)
    upstream_rate_limit_count: int = os.getenv("UPSTREAM_RATE_LIMIT_COUNT", 5)
    upstream_rate_limit_window_seconds: float = os.getenv(
        "UPSTREAM_RATE_LIMIT_WINDOW_SECONDS", 1
    )
    upstream_retry_attempts: int = os.getenv("UPSTREAM_RETRY_ATTEMPTS")
    upstream_retry_base_delay_seconds: float = os.getenv(
        "UPSTREAM_RETRY_BASE_DELAY_SECONDS", 0.5
    )
    upstream_retry_max_delay_seconds: float = os.getenv(
        "UPSTREAM_RETRY_MAX_DELAY_SECONDS", 4
    )
    log_body_preview_chars: int = os.getenv("LOG_BODY_PREVIEW_CHARS", 300)


settings = Settings()
