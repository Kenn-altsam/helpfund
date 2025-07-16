# companies/models.py

"""
SQLAlchemy models for companies

Defines the database schema for company data.
"""

from sqlalchemy import Column, String, Float
# NOTE: Removed unused imports like Integer, Float, Date, etc.

# Make sure you import 'Base' from your database setup file
from ..core.database import Base


class Company(Base):
    """Company model for storing company information"""
    
    __tablename__ = "companies"
    
    # --- Correct columns that ACTUALLY exist in your database ---
    # These 8 columns match the list you provided.
    
    bin_number = Column("BIN", String(12), primary_key=True, index=True)
    company_name = Column("Company", String(255), nullable=False, index=True)
    oked_code = Column("OKED", String(50), index=True)
    activity = Column("Activity", String(255), index=True)
    kato_code = Column("KATO", String(50), index=True)
    locality = Column("Locality", String(100), index=True)
    krp_code = Column("KRP", String(50))
    company_size = Column("Size", String(50), index=True)
    
    tax_data_2023 = Column("tax_data_2023", Float, nullable=True)
    tax_data_2024 = Column("tax_data_2024", Float, nullable=True)
    tax_data_2025 = Column("tax_data_2025", Float, nullable=True)
    phone = Column("phone", String(100), nullable=True)
    email = Column("email", String(255), nullable=True)
    website = Column("website", String(255), nullable=True)
    
    # --- REMOVED columns that DO NOT exist in your database ---
    # The following fields were causing the "UndefinedColumn" errors and have been deleted.
    
    # REMOVED: location = Column("location", ...)
    # REMOVED: tax_payment_2021 = Column(Float)
    # REMOVED: tax_payment_2022 = Column(Float)
    # REMOVED: tax_payment_2023 = Column(Float)
    # REMOVED: tax_payment_2024 = Column(Float)
    # REMOVED: tax_payment_2025 = Column(Float)
    # REMOVED: degreeofrisk = Column(String(100))
    # REMOVED: executive = Column(String(255))
    # REMOVED: phone = Column(String(100))
    # REMOVED: email = Column(String(255))
    
    def __repr__(self):
        return f"<Company(company_name='{self.company_name}', bin_number='{self.bin_number}')>"