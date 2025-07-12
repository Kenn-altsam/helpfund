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
    
    # Tell SQLAlchemy that "BIN" IS the primary key.
    # It will now use this column for identification and stop looking for 'id'.
    bin_number = Column("BIN", String(12), primary_key=True, index=True)
    company_name = Column("Company", String(255), nullable=False, index=True)
    oked_code = Column("OKED", String(50), index=True)
    activity = Column("Activity", String(255), index=True)
    kato_code = Column("KATO", String(50), index=True)
    locality = Column("Locality", String(100), index=True)
    krp_code = Column("KRP", String(50))
    company_size = Column("Size", String(50), index=True)
    
    # Newly-added extended columns matching the latest database schema / CSV imports
    location = Column("location", String(255), index=True)

    # Tax payment data for recent years
    tax_payment_2021 = Column(Float)
    tax_payment_2022 = Column(Float)
    tax_payment_2023 = Column(Float)
    tax_payment_2024 = Column(Float)
    tax_payment_2025 = Column(Float)

    # Additional metadata pulled from CSV
    degreeofrisk = Column(String(100))
    executive = Column(String(255))
    phone = Column(String(100))
    email = Column(String(255))
    
    # --- Tax information columns (currently omitted because they are not present in the live DB) ---
    # If / when the database is migrated to include налоговые поля, these columns can be re-enabled.
    
    def __repr__(self):
        return f"<Company(company_name='{self.company_name}', bin_number='{self.bin_number}')>" 