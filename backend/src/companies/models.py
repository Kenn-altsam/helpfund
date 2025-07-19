# companies/models.py

"""
SQLAlchemy models for companies

Defines the database schema for company data.
"""

from sqlalchemy import Column, String, Integer, Text, Float, DateTime, UUID, BigInteger
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.sql import func

# Make sure you import 'Base' from your database setup file
from ..core.database import Base


class Company(Base):
    """Company model for storing company information"""
    
    __tablename__ = "companies"
    
    # Primary key - using UUID as per actual database schema
    id = Column(PostgresUUID, primary_key=True, server_default=func.gen_random_uuid())
    
    # Core company information (quoted column names as per database schema)
    bin_number = Column("BIN", String(12), index=True)
    company_name = Column("Company", String(255), nullable=False, index=True)
    oked_code = Column("OKED", String(50), index=True)
    activity = Column("Activity", String(255), index=True)
    kato_code = Column("KATO", String(50), index=True)
    locality = Column("Locality", String(100), index=True)
    krp_code = Column("KRP", String(50))
    company_size = Column("Size", String(50), index=True)
    
    # Note: phone and email columns don't exist in actual database schema
    # These fields are handled in the service layer using other available data
    # Note: These columns don't exist in the actual database schema
    # degreeofrisk = Column(Text)
    # executive = Column(Text)
    # location = Column(String(255))
    
    # Tax data fields (matching actual database schema) - now BIGINT
    tax_data_2023 = Column("tax_data_2023", BigInteger, nullable=True)
    tax_data_2024 = Column("tax_data_2024", BigInteger, nullable=True)
    tax_data_2025 = Column("tax_data_2025", BigInteger, nullable=True)
    
    # Legacy fields for backward compatibility (these columns don't exist in actual DB)
    # contacts = Column("contacts", Text, nullable=True)
    # website = Column("website", Text, nullable=True)
    
    def __repr__(self):
        return f"<Company(company_name='{self.company_name}', bin_number='{self.bin_number}')>"