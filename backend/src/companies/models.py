# companies/models.py

"""
SQLAlchemy models for companies

Defines the database schema for company data.
"""

from sqlalchemy import Column, String, Integer, Text, Float, DateTime, UUID
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.sql import func

# Make sure you import 'Base' from your database setup file
from ..core.database import Base


class Company(Base):
    """Company model for storing company information"""
    
    __tablename__ = "companies"
    
    # Primary key - using UUID as per actual database schema
    id = Column("id", PostgresUUID, primary_key=True, server_default=func.gen_random_uuid())
    
    # Core company information
    bin_number = Column("BIN", String(12), index=True)
    company_name = Column("Company", String(255), nullable=False, index=True)
    oked_code = Column("OKED", String(50), index=True)
    activity = Column("Activity", String(255), index=True)
    kato_code = Column("KATO", String(50), index=True)
    locality = Column("Locality", String(100), index=True)
    krp_code = Column("KRP", String(50))
    company_size = Column("Size", String(50), index=True)
    
    # Additional fields from actual database
    registered_at = Column("registered_at", DateTime(timezone=True), server_default=func.now())
    degreeofrisk = Column("degreeofrisk", Text)
    executive = Column("executive", Text)
    phone = Column("phone", Text)
    email = Column("email", Text)
    location = Column("location", String(255))
    
    # Legacy fields for backward compatibility
    tax_data_2023 = Column("tax_data_2023", Text, nullable=True)
    tax_data_2024 = Column("tax_data_2024", Text, nullable=True)
    tax_data_2025 = Column("tax_data_2025", Text, nullable=True)
    contacts = Column("contacts", Text, nullable=True)
    website = Column("website", Text, nullable=True)
    
    def __repr__(self):
        return f"<Company(company_name='{self.company_name}', bin_number='{self.bin_number}')>"