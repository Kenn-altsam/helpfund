# """
# Simplified configuration management for the Ayala Foundation Backend using Pydantic Settings (v2).
#
# Focus: make the settings class explicit and rely on Pydantic's built-in parsing for
# comma-separated ALLOWED_ORIGINS. All other fields are loaded directly from the
# environment (optionally from a .env file).
# """

from functools import lru_cache
from typing import List, Any, Optional
from pydantic import PostgresDsn, Field, AliasChoices, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
import os


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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480 # This should be an int

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
    ALLOWED_ORIGINS: List[str] = Field(default=["*"])

    @model_validator(mode='before')
    @classmethod
    def validate_allowed_origins(cls, values):
        """Handle ALLOWED_ORIGINS parsing safely"""
        if isinstance(values, dict) and 'ALLOWED_ORIGINS' in values:
            origins = values['ALLOWED_ORIGINS']
            if origins is None or origins == "":
                values['ALLOWED_ORIGINS'] = ["*"]
            elif isinstance(origins, str):
                # Try to parse as JSON first (for ["url1", "url2"] format)
                try:
                    import json
                    parsed_origins = json.loads(origins)
                    if isinstance(parsed_origins, list):
                        values['ALLOWED_ORIGINS'] = [origin.strip() for origin in parsed_origins if origin.strip()]
                        return values
                except (json.JSONDecodeError, TypeError):
                    pass
                
                # Fall back to comma-separated string parsing
                values['ALLOWED_ORIGINS'] = [origin.strip() for origin in origins.split(',') if origin.strip()]
        return values

    # ------------------------------------------------------------------
    # Gemini AI
    # ------------------------------------------------------------------
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL_NAME: str = "gemini-1.5-flash"  # Default model

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
            return str(self.DATABASE_URL)
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    def model_post_init(self, __context: Any) -> None:
        """
        Validate and process settings after initialization.
        Pydantic-settings handles loading from .env and environment variables directly.
        This method is for post-validation logic or derived attributes, NOT for re-loading env vars.
        """
        # load_dotenv() is typically called once at application startup,
        # or Pydantic-settings might handle it internally based on config.
        # It's okay to leave it here, but the loop below is the problem.
        load_dotenv()

        # Basic validation
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL must be set in the environment.")
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY must be set in the environment.")
        if not self.GEMINI_API_KEY:
            print("⚠️  Warning: GEMINI_API_KEY is not set. AI functionality might be limited.")


    def print_settings(self):
        """Prints loaded settings for verification."""
        settings_to_print = self.model_dump()
        # Mask sensitive keys
        sensitive_keys = ["DATABASE_URL", "SECRET_KEY", "GEMINI_API_KEY"]
        for key in sensitive_keys:
            if key in settings_to_print and settings_to_print[key]:
                settings_to_print[key] = f"***{settings_to_print[key][-4:]}"

        print("\n--- Application Settings ---")
        for key, value in settings_to_print.items():
            print(f"  - {key}: {value}")
        print("--------------------------\n")
        
        # Provide feedback on loaded keys
        print("Key Loading Status:")
        print(f"  - Database URL Loaded: {'Yes' if self.DATABASE_URL else 'No'}")
        print(f"  - Secret Key Loaded: {'Yes' if self.SECRET_KEY else 'No'}")
        print(f"  - Gemini Key Loaded: {'Yes' if self.GEMINI_API_KEY else 'No'}")

@lru_cache()
def get_settings() -> Settings:
    """Returns the application settings, cached for performance."""
    print("⚙️  Loading settings...")
    settings = Settings()
    
    # --- Add detailed logging for Gemini settings ---
    print(f"  - Gemini Key Loaded: {'Yes' if settings.GEMINI_API_KEY else 'No'}")
    
    return settings