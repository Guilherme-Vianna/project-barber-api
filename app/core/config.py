from functools import lru_cache
from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

ASYNC_DRIVER = "postgresql+asyncpg"
POSTGRES_SCHEMES = {"postgres", "postgresql", "postgresql+psycopg", "postgresql+psycopg2"}
UNSUPPORTED_QUERY_KEYS = {"channel_binding"}
LOCAL_HOSTS = {None, "", "localhost", "127.0.0.1", "::1", "db"}


def to_async_database_url(url: str) -> str:
    parsed = make_url(url)
    if parsed.drivername in POSTGRES_SCHEMES:
        parsed = parsed.set(drivername=ASYNC_DRIVER)
    query = {key: value for key, value in parsed.query.items() if key not in UNSUPPORTED_QUERY_KEYS}
    sslmode = query.pop("sslmode", None)
    if sslmode is not None and "ssl" not in query:
        query["ssl"] = sslmode
    if "ssl" not in query and parsed.host not in LOCAL_HOSTS:
        query["ssl"] = "require"
    return parsed.set(query=query).render_as_string(hide_password=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "project-barber-api"
    environment: str = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "*"
    time_zone: str = "America/Sao_Paulo"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/app"
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_echo: bool = False
    run_migrations_on_startup: bool = True

    firebase_project_id: str | None = None
    google_application_credentials: str | None = None
    firebase_credentials_base64: str | None = None
    firebase_auth_emulator_host: str | None = None

    redis_url: str | None = None
    cache_ttl_seconds: int = 600
    k_revision: str = "local"

    @model_validator(mode="before")
    @classmethod
    def strip_whitespace(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        return {
            key: value.strip() if isinstance(value, str) else value for key, value in values.items()
        }

    @field_validator(
        "firebase_project_id",
        "google_application_credentials",
        "firebase_credentials_base64",
        "firebase_auth_emulator_host",
        "redis_url",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        return to_async_database_url(value)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
