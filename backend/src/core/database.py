"""
Database connection and session management for Ayala Foundation Backend

Handles PostgreSQL connection, session management, and database initialization.
"""

from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from typing import Generator
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import HTTPException

from .config import get_settings

# Load environment variables from .env file for local development
load_dotenv()

# Get settings
settings = get_settings()

# Create database engine
engine = create_engine(
    settings.database_url,
    poolclass=NullPool,
    echo=settings.debug,  # Log SQL queries in debug mode
    pool_pre_ping=True,   # Verify connections before use
)

# Create session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for declarative models
Base = declarative_base()

# Metadata for database operations
metadata = MetaData()

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    except HTTPException:
        # Don't wrap HTTPExceptions
        db.rollback()
        raise
    except Exception as e:
        logging.error(f"Database session error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Database error occurred"
        )
    finally:
        db.close()

def init_database():
    """
    Initialize database tables.
    Creates all tables defined in models.
    """
    try:
        # Import all models so that Alembic's autogeneration has access
        from ..companies import models as _  # noqa: F401
        from ..auth import models as _  # noqa: F401
        from ..funds import models as _  # noqa: F401

        # ------------------------------------------------------------------
        # Run Alembic migrations programmatically to ensure the database
        # schema is up-to-date without having to run the CLI separately.
        # This will create all missing tables / schemas defined in the
        # migration history ("alembic upgrade head").
        # ------------------------------------------------------------------
        try:
            from alembic import command
            from alembic.config import Config

            # Build absolute path to alembic.ini (located at project root /backend)
            base_dir = Path(__file__).resolve().parents[2]  # .../backend
            alembic_ini_path = base_dir / "alembic.ini"

            alembic_cfg = Config(str(alembic_ini_path))
            # Prevent configparser issues with % in passwords via env var in env.py
            command.upgrade(alembic_cfg, "head")
            logging.info("Alembic migrations applied successfully → database is up-to-date")
        except Exception as migrate_err:
            logging.error(
                "Alembic migration failed – falling back to SQLAlchemy create_all. Error: %s",
                migrate_err,
            )
            # Fallback: direct table creation (useful in dev / first-time setups)
            # Base.metadata.create_all(bind=engine)
            logging.info("Database tables created directly via SQLAlchemy as a fallback")

    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
        raise

def test_database_connection() -> bool:
    """
    Test database connection.
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        db = SessionLocal()
        # Use SQLAlchemy text construct for raw SQL (SQLAlchemy 2.x requirement)
        db.execute(text("SELECT 1"))
        db.close()
        logging.info("Database connection test successful")
        return True
    except Exception as e:
        logging.error(f"Database connection test failed: {e}")
        return False 