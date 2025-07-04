"""
API Router for company-related endpoints

Provides endpoints for searching and retrieving company data.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
import sys
from pathlib import Path

from .models import Company
from .service import CompanyService
from ..core.database import get_db
from ..core.translation_service import CityTranslationService
from ..ai_conversation.models import APIResponse

# Ensure project root (parent of src) is on Python path so that the top-level
# `parser` package with the KGD scraping utilities can be imported.
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from parser import KGDTaxParser as KGDParser  # noqa: E402

# Create router
router = APIRouter(
    prefix="/companies",
    tags=["Companies"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"}
    }
)


@router.get(
    "/search",
    summary="Search Companies",
    description="Search companies by location, name, or other criteria. Location names in English or other languages are automatically translated to Russian. When responding to user, give location in the language of the user."
)
async def search_companies(
    location: Optional[str] = Query(None, description="Location to search (city, region, or area). English names like 'Almaty' are automatically translated to Russian 'Алматы'"),
    company_name: Optional[str] = Query(None, description="Company name to search"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    db: Session = Depends(get_db)
):
    """
    Search companies based on location or name
    
    Args:
        location: Location filter (searches in Locality field).Location names in English or other languages are automatically translated to Russian. When responding to user, give location in the language of the user."
        company_name: Company name filter
        limit: Maximum number of results
        db: Database session
        
    Returns:
        List of companies matching the criteria
    """
    try:
        company_service = CompanyService(db)
        companies = await company_service.search_companies(
            location=location,
            company_name=company_name,
            limit=limit
        )
        
        return APIResponse(
            status="success",
            data=companies,
            message=f"Found {len(companies)} companies"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search companies: {str(e)}"
        )


@router.get(
    "/by-location/{location}",
    summary="Get Companies by Location",
    description="Get all companies in a specific location. Location names in English or other languages are automatically translated to Russian. When responding to user, give location in the language of the user."
)
async def get_companies_by_location(
    location: str,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results"),
    db: Session = Depends(get_db)
):
    """
    Get companies by specific location
    
    Args:
        location: Location name (city, region, or area). English names are automatically translated to Russian.
        limit: Maximum number of results
        db: Database session
        
    Returns:
        List of companies in the specified location
    """
    try:
        company_service = CompanyService(db)
        companies = await company_service.get_companies_by_location(location, limit)
        
        if not companies:
            raise HTTPException(
                status_code=404,
                detail=f"No companies found in location: {location}"
            )
            
        return APIResponse(
            status="success",
            data=companies,
            message=f"Found {len(companies)} companies in {location}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get companies by location: {str(e)}"
        )


@router.get(
    "/{company_id}",
    summary="Get Company Details",
    description="Get detailed information about a specific company"
)
async def get_company_details(
    company_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed company information
    
    Args:
        company_id: Company UUID
        db: Database session
        
    Returns:
        Detailed company information
    """
    try:
        company_service = CompanyService(db)
        company = await company_service.get_company_by_id(company_id)
        
        if not company:
            raise HTTPException(
                status_code=404,
                detail=f"Company not found with ID: {company_id}"
            )
            
        return APIResponse(
            status="success",
            data=company,
            message="Company details retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get company details: {str(e)}"
        )


@router.get(
    "/locations/list",
    summary="Get Available Locations",
    description="Get list of all available locations with company counts"
)
async def get_locations(
    db: Session = Depends(get_db)
):
    """
    Get list of available locations with company counts
    
    Args:
        db: Database session
        
    Returns:
        List of locations with company counts
    """
    try:
        company_service = CompanyService(db)
        locations = await company_service.get_all_locations()
        
        return APIResponse(
            status="success",
            data=locations,
            message=f"Found {len(locations)} locations"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get locations: {str(e)}"
        )


@router.get(
    "/translations/supported-cities",
    summary="Get Supported City Translations",
    description="Get list of English city names that are automatically translated to Russian"
)
async def get_supported_city_translations():
    """
    Get list of supported city name translations
    
    Returns:
        List of English city names that have Russian translations
    """
    try:
        supported_cities = CityTranslationService.get_supported_cities()
        
        # Create a sample of translations for display
        sample_translations = {}
        for city in supported_cities[:20]:  # Show first 20 as examples
            sample_translations[city] = CityTranslationService.translate_city_name(city)
        
        return APIResponse(
            status="success",
            data={
                "total_supported": len(supported_cities),
                "supported_cities": supported_cities,
                "sample_translations": sample_translations
            },
            message=f"Found {len(supported_cities)} supported city translations"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get supported translations: {str(e)}"
        )


@router.post(
    "/translations/translate-city",
    summary="Translate City Name",
    description="Translate an English city name to Russian"
)
async def translate_city_name(
    city_name: str = Query(..., description="City name to translate")
):
    """
    Translate a city name to Russian
    
    Args:
        city_name: English city name to translate
        
    Returns:
        Translation result
    """
    try:
        translated = CityTranslationService.translate_city_name(city_name)
        all_variations = CityTranslationService.get_all_possible_names(city_name)
        
        return APIResponse(
            status="success",
            data={
                "original": city_name,
                "translated": translated,
                "was_translated": translated != city_name,
                "all_search_variations": all_variations
            },
            message="Translation completed successfully"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to translate city name: {str(e)}"
        )


@router.get(
    "/tax/{bin_number}",
    summary="Get Tax Payment Data",
    description="Retrieve tax payment data for a company from the KGD (tax authority) website. If a 2captcha API key is configured in the environment (`CAPTCHA_API_KEY`), CAPTCHA solving is automatic; otherwise, the service will prompt for manual CAPTCHA entry in the browser window that appears."
)
async def get_tax_payment_data(
    bin_number: str,
):
    """Fetches tax payment and VAT-refund data for the specified BIN by launching a Chromium browser via Playwright and scraping the KGD site."""
    parser = KGDParser()  # auto mode – uses 2captcha if available
    try:
        result = await parser.search_company(bin_number)
    finally:
        # Ensure browser is closed even on error
        await parser.close()

    if result.get("status") == "success":
        return APIResponse(
            status="success",
            data=result["tax_data"],
            message="Tax data retrieved successfully"
        )

    # Something went wrong – propagate the error
    raise HTTPException(
        status_code=400,
        detail=f"Failed to retrieve tax data: {result.get('error', 'Unknown error')}"
    ) 