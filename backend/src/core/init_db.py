"""
Database initialization script for Ayala Foundation Backend

Script to initialize database tables and test database connectivity.
"""

import logging
import sys
from sqlalchemy import text

from .database import engine, SessionLocal, test_database_connection
from .config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_tables():
    """Create all database tables"""
    try:
        # Import all models to register them
        from ..companies.models import Company, Location
        from ..auth.models import User
        from ..funds.models import FundProfile
        
        # Import Base after models
        from .database import Base
        
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to create database tables: {e}")
        raise


def test_connection():
    """Test database connection"""
    logger.info("Testing database connection...")
    
    try:
        settings = get_settings()
        logger.info(f"Connecting to database: {settings.db_host}:{settings.db_port}/{settings.db_name}")
        
        # Test basic connection
        with SessionLocal() as db:
            result = db.execute(text("SELECT version()"))
            version = result.scalar()
            logger.info(f"✅ Database connection successful")
            logger.info(f"PostgreSQL version: {version}")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False


def init_database():
    """Initialize the complete database setup"""
    logger.info("🚀 Starting database initialization...")
    
    # Test connection first
    if not test_connection():
        logger.error("Cannot proceed without database connection")
        sys.exit(1)
    
    # Create tables
    create_tables()
    
    logger.info("🎉 Database initialization completed successfully!")


if __name__ == "__main__":
    init_database() 