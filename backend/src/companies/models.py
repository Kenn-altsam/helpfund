"""
SQLAlchemy models for companies

Defines the database schema for company data.
"""

from sqlalchemy import Column, String, Integer, Float, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from ..core.database import Base


class Company(Base):
    """Company model for storing company information"""
    
    __tablename__ = "companies"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Company information based on provided columns
    bin_number = Column("BIN", String(12), index=True)
    company_name = Column("Company", String(255), nullable=False, index=True)
    oked_code = Column("OKED", String(50), index=True)
    activity = Column("Activity", String(255), index=True)
    kato_code = Column("KATO", String(50), index=True)
    locality = Column("Locality", String(100), index=True)
    krp_code = Column("KRP", String(50))
    company_size = Column("Size", String(50), index=True)
    
    # --- Tax information columns (currently omitted because they are not present in the live DB) ---
    # If / when the database is migrated to include налоговые поля, these columns can be re-enabled.
    
    def __repr__(self):
        return f"<Company(id={self.id}, company_name='{self.company_name}', bin_number='{self.bin_number}')>" 