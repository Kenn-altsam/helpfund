"""
Configuration management for Ayala Foundation Backend using Pydantic Settings (v2).

Loads environment variables from a .env file (if present) and provides
validated, typed access to configuration values throughout the backend.
"""

from functools import lru_cache
from typing import List

from pydantic import PostgresDsn, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables (validated)."""

    # Pydantic-settings configuration: where to read env vars from
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ---------------------------------------------------------------------
    # OpenAI
    # ---------------------------------------------------------------------
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    # ---------------------------------------------------------------------
    # FastAPI / Server
    # ---------------------------------------------------------------------
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    debug: bool = Field(default=True, alias="DEBUG")

    # ---------------------------------------------------------------------
    # CORS
    # ---------------------------------------------------------------------
    allowed_origins: List[str] = Field(default_factory=lambda: ["*"], alias="ALLOWED_ORIGINS")
    allow_credentials: bool = Field(default=True, alias="ALLOW_CREDENTIALS")
    allow_methods: List[str] = Field(default_factory=lambda: [
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "OPTIONS",
        "PATCH",
    ])
    allow_headers: List[str] = Field(default_factory=lambda: ["*"], alias="ALLOW_HEADERS")

    # ---------------------------------------------------------------------
    # Database
    # ---------------------------------------------------------------------
    database_url: PostgresDsn | None = Field(default=None, alias="DATABASE_URL")
    db_host: str = Field(default="localhost", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_name: str = Field(default="nFac_server", alias="DB_NAME")
    db_user: str = Field(default="postgres", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")

    # ---------------------------------------------------------------------
    # JWT / Auth
    # ---------------------------------------------------------------------
    secret_key: str = Field(default="your-secret-key-please-change-in-production", alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # ---------------------------------------------------------------------
    # Validators / post-processing
    # ---------------------------------------------------------------------
    @staticmethod
    def _assemble_db_url(values: "Settings") -> str:
        return (
            f"postgresql://{values.db_user}:{values.db_password}"  # type: ignore[attr-defined]
            f"@{values.db_host}:{values.db_port}/{values.db_name}"
        )

    # pydantic v2: model_post_init runs after validation
    def model_post_init(self, __context):  # noqa: D401, N802
        # Build DATABASE_URL if not provided.
        if self.database_url is None:
            object.__setattr__(self, "database_url", self._assemble_db_url(self))

        # Warn if critical values are missing or insecure.
        if not self.openai_api_key:
            print("⚠️  Warning: OPENAI_API_KEY environment variable is not set")
            print("    Please set it using: export OPENAI_API_KEY=<your_key_here>")

        if self.secret_key == "your-secret-key-please-change-in-production":
            print("⚠️  Warning: Using default SECRET_KEY. Set a secure SECRET_KEY in production!")


# -------------------------------------------------------------------------
# Cached accessor (keeps a single settings instance alive for the process)
# -------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return an application-wide, cached Settings instance."""
    return Settings() 