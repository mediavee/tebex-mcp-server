"""Typed configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server settings.

    Values are loaded from process environment, then ``.env`` (if present).
    Field names use snake_case; env vars use SCREAMING_SNAKE_CASE.

    The Tebex secret is **not** loaded here — it is provided per-request via
    the ``X-Tebex-Secret`` HTTP header so a single instance can serve any
    number of stores.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    mcp_auth_token: SecretStr = Field(..., description="Bearer token for HTTP clients.")

    http_host: str = Field("0.0.0.0", description="HTTP bind host.")
    http_port: int = Field(3000, ge=1, le=65535, description="HTTP bind port.")

    log_level: str = Field("INFO", description="Logger level (DEBUG, INFO, WARNING, ERROR).")
    log_json: bool = Field(False, description="Emit logs as JSON.")


def load_settings() -> Settings:
    return Settings()
