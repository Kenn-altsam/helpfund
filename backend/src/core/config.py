"""
Configuration management for Ayala Foundation Backend

Configuration management using environment variables with database support.
"""

import os
from typing import List
from functools import lru_cache
from dataclasses import dataclass


@dataclass
class Settings:
    """Application settings loaded from environment variables"""
    
    def __init__(self):
        # Try to load environment variables from .env file if python-dotenv is available
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            # If python-dotenv is not available, just use system environment variables
            pass
        
        # OpenAI Configuration
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        if not self.openai_api_key:
            print("Warning: OPENAI_API_KEY environment variable is not set")
            print("Please set it using: export OPENAI_API_KEY=your_key_here")
            # Don't raise error immediately, allow app to start for testing
        
        # FastAPI Configuration  
        self.host: str = os.getenv("HOST", "0.0.0.0")  # Allow external connections
        self.port: int = int(os.getenv("PORT", "8000"))  # Changed to 8000 to match frontend
        self.debug: bool = os.getenv("DEBUG", "True").lower() == "true"
        
        # CORS Configuration - Allow all origins in development
        # For production, specify exact domains
        origins_str = os.getenv("ALLOWED_ORIGINS", "*")  # Allow all origins for development
        if origins_str == "*":
            # Very permissive CORS for mobile development - allows any origin
            self.allowed_origins: List[str] = ["*"]
        else:
            self.allowed_origins: List[str] = [origin.strip() for origin in origins_str.split(",")]
        
        # Additional mobile-friendly settings
        self.allow_credentials: bool = os.getenv("ALLOW_CREDENTIALS", "true").lower() == "true"
        self.allow_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
        self.allow_headers: List[str] = ["*"]
        
        # Database Configuration
        self.database_url: str = os.getenv("DATABASE_URL", "")
        self.db_host: str = os.getenv("DB_HOST", "localhost")
        self.db_port: int = int(os.getenv("DB_PORT", "5432"))
        self.db_name: str = os.getenv("DB_NAME", "nFac_server")
        self.db_user: str = os.getenv("DB_USER", "postgres")
        self.db_password: str = os.getenv("DB_PASSWORD", "")
        
        # Build database URL if not provided
        if not self.database_url:
            self.database_url = f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        
        # JWT Authentication Configuration
        self.secret_key: str = os.getenv("SECRET_KEY", "your-secret-key-please-change-in-production")
        self.algorithm: str = os.getenv("ALGORITHM", "HS256")
        self.access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        
        if self.secret_key == "your-secret-key-please-change-in-production":
            print("Warning: Using default SECRET_KEY. Please set a secure SECRET_KEY in production!")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings() 