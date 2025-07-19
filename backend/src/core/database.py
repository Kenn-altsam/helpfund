"""
Database connection and session management for Ayala Foundation Backend

Handles PostgreSQL connection, session management, and database initialization.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import get_settings
from .database_config import get_database_config, optimize_database_connection

# Get the application settings
settings = get_settings()

# Get optimized database configuration
db_config = get_database_config()

# Use the synchronous 'create_engine' with optimized settings
# The database_url property in config.py should now produce
# a URL like 'postgresql://user:password@host/db'
engine = create_engine(
    settings.database_url,
    **db_config,  # Apply optimized configuration
)

# Use the standard synchronous SessionMaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# The Declarative Base is the same
Base = declarative_base()

# Apply database optimizations on startup
try:
    optimize_database_connection(engine)
except Exception as e:
    print(f"⚠️  Database optimization skipped: {e}")

# --- NEW Dependency Function ---
# This is the synchronous dependency we will use in our FastAPI routes.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()