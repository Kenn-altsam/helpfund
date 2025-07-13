# """
# Simplified configuration management for the Ayala Foundation Backend using Pydantic Settings (v2).
#
# Focus: make the settings class explicit and rely on Pydantic's built-in parsing for
# comma-separated ALLOWED_ORIGINS. All other fields are loaded directly from the
# environment (optionally from a .env file).
# """

from functools import lru_cache
from typing import List

from pydantic import PostgresDsn, Field, AliasChoices, model_validator
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
        env_nested_delimiter='__', # Added for robust parsing
    )

    # ------------------------------------------------------------------
    # Database
    # If DATABASE_URL is not provided directly, it can be assembled from the
    # individual connection parts defined below (legacy support).
    # ------------------------------------------------------------------
    DATABASE_URL: str | None = None

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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # ------------------------------------------------------------------
    # FastAPI / Server toggles
    # ------------------------------------------------------------------
    DEBUG: bool = True

    # ------------------------------------------------------------------
    # CORS
    # Pydantic automatically splits comma-separated strings for List[str]
    # when the value is a simple string.
    # Example: "https://example.com,https://myapp.com"
    # The custom validator is removed to rely on default behavior.
    # ------------------------------------------------------------------
    ALLOWED_ORIGINS: List[str] = []

    # ------------------------------------------------------------------
    # OpenAI - UPDATED FOR AZURE
    # ------------------------------------------------------------------
    OPENAI_API_KEY: str = ""
    AZURE_OPENAI_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_DEPLOYMENT_NAME: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-02-01"

    # ------------------------------------------------------------------
    # Backwards-compatibility helpers (legacy lowercase attributes)
    # ------------------------------------------------------------------
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ALLOW_CREDENTIALS: bool = True
    ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    ALLOW_HEADERS: List[str] = ["*"]

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            # Just return the URL as is
            return str(self.DATABASE_URL)

        # --- >>> THIS IS THE CRITICAL CHANGE <<< ---
        # Assemble a standard synchronous URL
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    def model_post_init(self, __context):
        # Updated check for Azure keys
        if not self.AZURE_OPENAI_KEY or not self.AZURE_OPENAI_ENDPOINT:
            print("⚠️  Warning: AZURE_OPENAI_KEY or AZURE_OPENAI_ENDPOINT is not set.")
        if "your-secret-key" in self.SECRET_KEY:
            print("⚠️  Warning: Using a default SECRET_KEY. Please set a secure one for production.")

@lru_cache()
def get_settings() -> Settings:
    """Returns the application settings, cached for performance."""
    print("⚙️  Loading settings...")
    settings = Settings()
    
    # --- Add detailed logging for Azure settings ---
    print(f"  - Azure Key Loaded: {'Yes' if settings.AZURE_OPENAI_KEY else 'No'}")
    print(f"  - Azure Endpoint Loaded: {settings.AZURE_OPENAI_ENDPOINT or 'Not Set'}")
    print(f"  - Azure Deployment Loaded: {settings.AZURE_OPENAI_DEPLOYMENT_NAME or 'Not Set'}")
    print(f"  - OpenAI Key (Legacy) Loaded: {'Yes' if settings.OPENAI_API_KEY else 'No'}")
    
    return settings