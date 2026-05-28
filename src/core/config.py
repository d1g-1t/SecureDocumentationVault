from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["dev", "test", "staging", "prod"] = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 18000
    app_debug: bool = False

    postgres_host: str = "localhost"
    postgres_port: int = 15432
    postgres_db: str = "securedocvault"
    postgres_user: str = "sdv"
    postgres_password: str = Field(..., repr=False)

    redis_host: str = "localhost"
    redis_port: int = 16379
    redis_password: str = Field(..., repr=False)
    redis_db: int = 0

    minio_endpoint: str = "localhost:19000"
    minio_public_endpoint: str = "http://localhost:19000"
    minio_root_user: str = Field(..., repr=False)
    minio_root_password: str = Field(..., repr=False)
    minio_bucket_documents: str = "securedocvault-docs"
    minio_secure: bool = False

    paseto_secret_key: str = Field(..., repr=False)
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 14

    celery_broker_url: str = "redis://:change-me@localhost:16379/0"
    celery_result_backend: str = "redis://:change-me@localhost:16379/1"

    otel_exporter_otlp_endpoint: str = "http://localhost:14317"
    otel_service_name: str = "securedocvault-api"
    otel_enabled: bool = True

    enable_log_masking: bool = True
    cors_allow_origins: list[str] = ["http://localhost:3000"]

    default_storage_class: str = "STANDARD"
    default_retention_mode: str = "GOVERNANCE"
    audit_chain_enabled: bool = True
    legal_hold_strict_mode: bool = True
    max_upload_size_mb: int = 100

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def redis_url(self) -> str:
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @computed_field
    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @model_validator(mode="after")
    def validate_paseto_key(self) -> "AppSettings":
        if len(self.paseto_secret_key) < 32:
            raise ValueError("PASETO_SECRET_KEY must be at least 32 characters")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "prod"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
