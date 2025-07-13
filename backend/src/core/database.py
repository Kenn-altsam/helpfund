"""
Database connection and session management for Ayala Foundation Backend

Handles PostgreSQL connection, session management, and database initialization.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import get_settings

# Get the application settings
settings = get_settings()

# Use the synchronous 'create_engine'
# The database_url property in config.py should now produce
# a URL like 'postgresql://user:password@host/db'
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True, # Good practice for long-running apps
)

# Use the standard synchronous SessionMaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# The Declarative Base is the same
Base = declarative_base()

# --- NEW Dependency Function ---
# This is the synchronous dependency we will use in our FastAPI routes.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()