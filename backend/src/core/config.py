# """
# Simplified configuration management for the Ayala Foundation Backend using Pydantic Settings (v2).

# Focus: make the settings class explicit and rely on Pydantic's built-in parsing for
# comma-separated ALLOWED_ORIGINS. All other fields are loaded directly from the
# environment (optionally from a .env file).
# """

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
        env_nested_delimiter='__', # Added for robust parsing
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
    ALLOWED_ORIGINS: List[str] = ["*"]

    # ------------------------------------------------------------------
    # OpenAI - UPDATED FOR AZURE
    # ------------------------------------------------------------------
    # --- Legacy key (can be removed if not used elsewhere) ---
    OPENAI_API_KEY: str = ""
    
    # +++ NEW AZURE SETTINGS +++
    AZURE_OPENAI_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_DEPLOYMENT_NAME: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-02-01" # A stable API version

    # ------------------------------------------------------------------
    # Backwards-compatibility helpers (legacy lowercase attributes)
    # ------------------------------------------------------------------
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ALLOW_CREDENTIALS: bool = True
    ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    ALLOW_HEADERS: List[str] = ["*"]

    # ------------------------------------------------------------------
    # Computed aliases and properties
    # ------------------------------------------------------------------
    
    # --- Azure Properties ---
    @property
    def azure_openai_key(self) -> str:
        return self.AZURE_OPENAI_KEY

    @property
    def azure_openai_endpoint(self) -> str:
        return self.AZURE_OPENAI_ENDPOINT

    @property
    def azure_openai_deployment_name(self) -> str:
        return self.AZURE_OPENAI_DEPLOYMENT_NAME
        
    @property
    def azure_openai_api_version(self) -> str:
        return self.AZURE_OPENAI_API_VERSION

    # --- Other Properties (kept for compatibility) ---
    @property
    def host(self) -> str: return self.HOST
    @property
    def port(self) -> int: return self.PORT
    @property
    def allowed_origins(self) -> List[str]: return self.ALLOWED_ORIGINS
    @property
    def allow_credentials(self) -> bool: return self.ALLOW_CREDENTIALS
    @property
    def allow_methods(self) -> List[str]: return self.ALLOW_METHODS
    @property
    def allow_headers(self) -> List[str]: return self.ALLOW_HEADERS
    @property
    def db_host(self) -> str: return self.DB_HOST
    @property
    def db_port(self) -> int: return self.DB_PORT
    @property
    def db_name(self) -> str: return self.DB_NAME
    @property
    def db_user(self) -> str: return self.DB_USER
    @property
    def db_password(self) -> str: return self.DB_PASSWORD
    @property
    def secret_key(self) -> str: return self.SECRET_KEY
    @property
    def algorithm(self) -> str: return self.ALGORITHM
    @property
    def access_token_expire_minutes(self) -> int: return self.ACCESS_TOKEN_EXPIRE_MINUTES
    @property
    def debug(self) -> bool: return self.DEBUG
    @property
    def openai_api_key(self) -> str: return self.OPENAI_API_KEY
    @property
    def database_url(self) -> str:
        if self.DATABASE_URL is not None:
            return str(self.DATABASE_URL)
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    def model_post_init(self, __context):
        # Updated check for Azure keys
        if not self.AZURE_OPENAI_KEY or not self.AZURE_OPENAI_ENDPOINT:
            print("⚠️  Warning: AZURE_OPENAI_KEY or AZURE_OPENAI_ENDPOINT is not set.")
        if "your-secret-key" in self.SECRET_KEY:
            print("⚠️  Warning: Using a default SECRET_KEY. Please set a secure one for production.")

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
        raise