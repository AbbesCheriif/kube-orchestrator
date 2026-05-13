"""Application settings loaded from environment variables and optional .env file."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global settings for kube-orchestrator, populated from env / .env file."""

    kubeconfig: str | None = None
    kube_context: str | None = None
    kube_namespace: str = "default"
    log_level: str = "INFO"
    log_format: str = "json"
    retry_max_attempts: int = 3
    default_timeout: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
