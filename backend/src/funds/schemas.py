"""
Pydantic schemas for fund profiles

Request/Response models for fund profile endpoints.
"""

from pydantic import BaseModel, EmailStr
from typing import Optional


class FundProfileBase(BaseModel):
    """Base fund profile schema"""
    fund_name: str
    fund_description: Optional[str] = None
    fund_email: Optional[EmailStr] = None


class FundProfileCreate(FundProfileBase):
    """Schema for fund profile creation"""
    pass


class FundProfileResponse(FundProfileBase):
    """Schema for fund profile response"""
    id: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True 