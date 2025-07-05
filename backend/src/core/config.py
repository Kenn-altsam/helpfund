"""
Simplified configuration management for the Ayala Foundation Backend using Pydantic Settings (v2).

Focus: make the settings class explicit and rely on Pydantic's built-in parsing for
comma-separated ALLOWED_ORIGINS. All other fields are loaded directly from the
environment (optionally from a .env file).
"""

from functools import lru_cache
from typing import List

from pydantic import PostgresDsn, Field, field_validator, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings validated and loaded from environment variables."""

    # ------------------------------------------------------------------
    # Base configuration for pydantic-settings
    # ------------------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # DB_HOST and db_host are treated the same
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Database
    # If DATABASE_URL is not provided directly, it can be assembled from the
    # individual connection parts defined below (legacy support).
    # ------------------------------------------------------------------
    DATABASE_URL: PostgresDsn | None = None

    # Individual parts (legacy)
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "nFac_server"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""

    # ------------------------------------------------------------------
    # JWT / Auth
    # ------------------------------------------------------------------
    # Try SECRET_KEY first for backwards-compatibility, fall back to JWT_SECRET_KEY
    SECRET_KEY: str = Field(..., validation_alias=AliasChoices("SECRET_KEY", "JWT_SECRET_KEY"))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ------------------------------------------------------------------
    # FastAPI / Server toggles
    # ------------------------------------------------------------------
    DEBUG: bool = True

    # ------------------------------------------------------------------
    # CORS
    # Pydantic automatically splits comma-separated strings for List[str]
    # Example: "https://example.com, https://myapp.com"
    # ------------------------------------------------------------------
    ALLOWED_ORIGINS: List[str] = ["*"]

    # Parse comma-separated strings like "http://localhost:3000,http://127.0.0.1:3000"
    # into a proper Python list so we remain backwards-compatible with the old env syntax.
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def split_allowed_origins(cls, v):  # noqa: D401
        if isinstance(v, str):
            # Support empty strings by filtering out blanks after strip
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ------------------------------------------------------------------
    # OpenAI
    # ------------------------------------------------------------------
    OPENAI_API_KEY: str = ""

    # ------------------------------------------------------------------
    # Backwards-compatibility helpers (legacy lowercase attributes)
    # ------------------------------------------------------------------
    # FastAPI / server networking
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS extras used in middleware configuration
    ALLOW_CREDENTIALS: bool = True
    ALLOW_METHODS: List[str] = [
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "OPTIONS",
        "PATCH",
    ]
    ALLOW_HEADERS: List[str] = ["*"]

    # ------------------------------------------------------------------
    # Computed aliases – keep the rest of the codebase untouched
    # ------------------------------------------------------------------
    @property
    def host(self) -> str:
        return self.HOST

    @property
    def port(self) -> int:
        return self.PORT

    @property
    def allowed_origins(self) -> List[str]:
        return self.ALLOWED_ORIGINS

    @property
    def allow_credentials(self) -> bool:
        return self.ALLOW_CREDENTIALS

    @property
    def allow_methods(self) -> List[str]:
        return self.ALLOW_METHODS

    @property
    def allow_headers(self) -> List[str]:
        return self.ALLOW_HEADERS

    # ------------------------------------------------------------------
    # Database helper properties (legacy attribute names)
    # ------------------------------------------------------------------
    @property
    def db_host(self) -> str:  # noqa: D401
        return self.DB_HOST

    @property
    def db_port(self) -> int:  # noqa: D401
        return self.DB_PORT

    @property
    def db_name(self) -> str:  # noqa: D401
        return self.DB_NAME

    @property
    def db_user(self) -> str:  # noqa: D401
        return self.DB_USER

    @property
    def db_password(self) -> str:  # noqa: D401
        return self.DB_PASSWORD

    # Provide lowercase alias expected elsewhere
    @property
    def database_url(self) -> str:  # noqa: D401
        """Return a ready-to-use DATABASE_URL.

        Priority:
        1. Explicit DATABASE_URL env variable.
        2. Construct from individual DB_* parts for backwards compatibility.
        """
        if self.DATABASE_URL is not None:
            return str(self.DATABASE_URL)
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # ------------------------------------------------------------------
    # Security helpers (legacy lowercase attribute names)
    # ------------------------------------------------------------------
    @property
    def secret_key(self) -> str:  # noqa: D401
        return self.SECRET_KEY

    @property
    def algorithm(self) -> str:  # noqa: D401
        return self.ALGORITHM

    @property
    def access_token_expire_minutes(self) -> int:  # noqa: D401
        return self.ACCESS_TOKEN_EXPIRE_MINUTES

    # ------------------------------------------------------------------
    # Post-initialisation validation / warnings
    # ------------------------------------------------------------------
    def model_post_init(self, __context):  # noqa: D401
        if not self.OPENAI_API_KEY:
            print("⚠️  Warning: OPENAI_API_KEY is not set.")
        if "your-secret-key" in self.SECRET_KEY:
            print(
                "⚠️  Warning: Using a default SECRET_KEY. Please set a secure one for production."
            )

    # ------------------------------------------------------------------
    # Misc lowercase aliases
    # ------------------------------------------------------------------
    @property
    def debug(self) -> bool:  # noqa: D401
        return self.DEBUG

    @property
    def openai_api_key(self) -> str:  # noqa: D401
        return self.OPENAI_API_KEY


# ----------------------------------------------------------------------
# Cached accessor (keeps a single settings instance alive for the process)
# ----------------------------------------------------------------------
@lru_cache()
def get_settings() -> Settings:
    """Return an application-wide, cached Settings instance."""

    print("⚙️  Loading settings…")
    try:
        settings = Settings()
        print("✅ Settings loaded successfully.")
        return settings
    except Exception as e:
        print(f"❌ FATAL: Failed to load settings. Error: {e}")
        # Re-raise to expose validation errors clearly
        raise 