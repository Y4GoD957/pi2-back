import json
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "EduCenso Analytics API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/educenso"
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_secret_key: str | None = None
    supabase_jwt_secret: str | None = None
    local_dev_cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            normalized_value = value.strip()
            if normalized_value.startswith("["):
                try:
                    parsed_value = json.loads(normalized_value)
                except json.JSONDecodeError:
                    parsed_value = None
                else:
                    if isinstance(parsed_value, list):
                        return [item.strip() for item in parsed_value if isinstance(item, str) and item.strip()]

            return [item.strip() for item in normalized_value.split(",") if item.strip()]
        return value

    @field_validator("local_dev_cors_origins", mode="before")
    @classmethod
    def parse_local_dev_cors_origins(cls, value):
        return cls.parse_cors_origins(value)

    @property
    def effective_cors_origins(self) -> list[str]:
        origins = list(self.cors_origins)
        if self.app_env != "development":
            return origins

        for origin in self.local_dev_cors_origins:
            if origin not in origins:
                origins.append(origin)

        return origins
@lru_cache
def get_settings() -> Settings:
    return Settings()
