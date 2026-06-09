from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    provider_name: str = "openliga"
    openliga_base_url: str = "https://api.openligadb.de"
    upstream_timeout_seconds: float = 10.0
    upstream_rate_limit_count: int = 5
    upstream_rate_limit_window_seconds: float = 1.0
    upstream_retry_attempts: int = 3
    upstream_retry_base_delay_seconds: float = 0.5
    upstream_retry_max_delay_seconds: float = 4.0
    log_body_preview_chars: int = 300


settings = Settings()
