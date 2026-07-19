"""Typed runtime configuration with local-first, secret-safe defaults."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_frontend_dist() -> Path:
    return Path(__file__).resolve().parent / "static"


class Settings(BaseSettings):
    """Dataset Foundry settings loaded from ``DATASET_FOUNDRY_*`` variables.

    Provider credentials intentionally remain ``SecretStr`` instances and are
    never part of the public provider-status response.
    """

    model_config = SettingsConfigDict(
        env_prefix="DATASET_FOUNDRY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    app_name: str = "Dataset Foundry"
    environment: Literal["development", "test", "container", "production"] = "development"
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65_535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    data_dir: Path = Path(".data")
    database_url: str | None = None
    artifact_dir: Path | None = None
    frontend_dist: Path = Field(default_factory=_default_frontend_dist)
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, ge=1, le=1024**3)
    max_seed_rows: int = Field(default=50_000, ge=1, le=1_000_000)

    default_provider: Literal["offline", "openai", "anthropic"] = "offline"
    openai_model: str = "gpt-5.6-luna"
    anthropic_model: str = "claude-sonnet-5"
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "OPENAI_API_KEY",
            "DATASET_FOUNDRY_OPENAI_API_KEY",
        ),
    )
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "ANTHROPIC_API_KEY",
            "DATASET_FOUNDRY_ANTHROPIC_API_KEY",
        ),
    )
    provider_retry_base_seconds: float = Field(default=0.25, ge=0, le=30)
    provider_timeout_seconds: float = Field(default=120, gt=0, le=600)
    provider_max_output_tokens: int = Field(default=8_192, ge=256, le=64_000)

    worker_id: str = "local-worker"
    worker_poll_seconds: float = Field(default=0.5, ge=0.01, le=60)
    worker_lease_seconds: int = Field(default=120, ge=10, le=3_600)
    worker_heartbeat_seconds: int = Field(default=30, ge=1, le=1_800)

    api_key: SecretStr | None = None
    allow_unauthenticated_container_loopback: bool = False
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:8765",
            "http://localhost:8765",
        ]
    )

    @field_validator("host", "worker_id")
    @classmethod
    def non_blank_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("api_key", "openai_api_key", "anthropic_api_key", mode="before")
    @classmethod
    def blank_secrets_are_unset(cls, value: str | SecretStr | None) -> SecretStr | None:
        """Treat whitespace-only credentials as absent, never as valid empty keys."""

        if value is None:
            return None
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else value
        normalized = raw_value.strip()
        return SecretStr(normalized) if normalized else None

    @field_validator("cors_origins")
    @classmethod
    def cors_origins_are_explicit(cls, values: list[str]) -> list[str]:
        if not values or any(not value.strip() for value in values):
            raise ValueError("cors_origins must contain explicit non-blank origins")
        if "*" in values:
            raise ValueError("wildcard CORS is not allowed")
        return list(dict.fromkeys(value.rstrip("/") for value in values))

    @model_validator(mode="after")
    def non_loopback_binding_requires_auth(self) -> Settings:
        loopback_hosts = {"127.0.0.1", "localhost", "::1"}
        container_wildcard = self.host == "0.0.0.0"  # noqa: S104  # nosec B104
        container_loopback_publish = (
            self.environment == "container"
            and container_wildcard
            and self.allow_unauthenticated_container_loopback
        )
        if (
            self.host not in loopback_hosts
            and self.api_key is None
            and not container_loopback_publish
        ):
            raise ValueError("non-loopback binding requires DATASET_FOUNDRY_API_KEY")
        if self.worker_heartbeat_seconds >= self.worker_lease_seconds:
            raise ValueError("worker heartbeat must be shorter than the lease")
        return self

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'dataset-foundry.sqlite3').resolve()}"

    @property
    def resolved_artifacts_dir(self) -> Path:
        return (self.artifact_dir or self.data_dir / "artifacts").resolve()

    def provider_configured(self, provider: str) -> bool:
        """Return credential availability without exposing credential values."""

        if provider == "offline":
            return True
        if provider == "openai":
            return self.openai_api_key is not None
        if provider == "anthropic":
            return self.anthropic_api_key is not None
        return False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return one validated settings object per process."""

    return Settings()


def clear_settings_cache() -> None:
    """Reset the settings cache for tests and explicit runtime reconfiguration."""

    get_settings.cache_clear()
