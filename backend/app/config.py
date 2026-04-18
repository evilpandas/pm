from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    pm_username: str = "jared"
    pm_password: str = "password"
    pm_db_path: str = ""
    openrouter_api_key: str = ""
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440


settings = Settings()


def reload_settings() -> None:
    global settings
    settings = Settings()


def validate_settings() -> None:
    import logging

    errors = []
    warnings = []

    if not settings.openrouter_api_key:
        warnings.append("OPENROUTER_API_KEY is not set - AI chat functionality will not work")

    if not settings.jwt_secret_key:
        errors.append("JWT_SECRET_KEY is not set - generate one with: openssl rand -hex 32")

    if not settings.pm_password:
        errors.append("PM_PASSWORD is not set")

    if warnings:
        logger = logging.getLogger("pm_backend")
        for warning in warnings:
            logger.warning(warning)

    if errors:
        error_message = "Configuration errors:\n" + "\n".join(f"  - {err}" for err in errors)
        raise ValueError(error_message)
