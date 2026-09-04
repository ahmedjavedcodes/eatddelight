from functools import lru_cache
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    api_v1_prefix: str = "/api/v1"

    database_url: str
    test_database_url: str | None = None

    # NoDecode: keep pydantic-settings from JSON-parsing the raw env value so the
    # validator below can accept a plain comma-separated string.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    owner_email: str
    owner_password: str
    owner_name: str = "Owner"

    whatsapp_number: str = "923122252915"

    rate_limit_public_write: str = "10/minute"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: Any) -> Any:
        """Accept a comma-separated string in addition to a JSON list."""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return value
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
