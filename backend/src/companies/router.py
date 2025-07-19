"""
API Router for company-related endpoints

Provides endpoints for searching and retrieving company data.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import text
import sys
from pathlib import Path
import logging
import traceback
import time

from .service import CompanyService
from ..core.database import get_db
from ..core.translation_service import CityTranslationService
from ..ai_conversation.models import APIResponse
from ..auth.dependencies import get_current_user
from ..auth.models import User

# Ensure project root (parent of src) is on Python path so that the top-level
# `parser` package with the KGD scraping utilities can be imported.
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

# Create router
router = APIRouter(
    prefix="/companies",
    tags=["Companies"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"}
    }
)

logging.basicConfig(level=logging.INFO)


@router.get(
    "/search",
    summary="Search Companies",
    description="Search companies by location, name, or other criteria. Location names in English or other languages are automatically translated to Russian. When responding to user, give location in the language of the user."
)
async def search_companies(
    location: Optional[str] = Query(
        None,
        description="Location to search (city, region, or area). English names like 'Almaty' are automatically translated to Russian 'Алматы'"
    ),
    company_name: Optional[str] = Query(None, description="Company name to search"),
    activity_keywords: Optional[List[str]] = Query(
        None,
        description=(
            "List of keywords to search in the company's activity/description field. "
            "Pass multiple values as repeated query parameters, e.g. `?activity_keywords=oil&activity_keywords=gas`, "
            "or as a comma-separated string `?activity_keywords=oil,gas`."
        )
    ),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results per page"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    db: Session = Depends(get_db)
):
    """
    Search companies based on location or name
    
    Args:
        location: Location filter (searches in Locality field).Location names in English or other languages are automatically translated to Russian. When responding to user, give location in the language of the user."
        company_name: Company name filter
        activity_keywords: List of keywords to search in the company's activity/description field
        limit: Maximum number of results per page
        page: Page number (1-based pagination)
        db: Database session
        
    Returns:
        List of companies matching the criteria with pagination metadata
    """
    start_time = time.time()
    logging.info(f"[COMPANIES][SEARCH] Request: location={location}, company_name={company_name}, activity_keywords={activity_keywords}, limit={limit}, page={page}")
    try:
        # Calculate offset from page number
        offset = (page - 1) * limit
        logging.info(f"[COMPANIES][SEARCH] Calculated offset={offset} from page={page}, limit={limit}")
        
        company_service = CompanyService(db)
        
        # Measure search_companies time
        search_start = time.time()
        companies = company_service.search_companies(
            location=location,
            company_name=company_name,
            activity_keywords=activity_keywords,
            limit=limit,
            offset=offset
        )
        search_time = time.time() - search_start
        logging.info(f"[DEBUG] Search companies time: {search_time:.2f}s")
        logging.info(f"[COMPANIES][SEARCH] Found {len(companies)} companies")
        
        # Measure count time
        count_start = time.time()
        total_count = company_service.get_total_company_count()
        count_time = time.time() - count_start
        logging.info(f"[DEBUG] Count time: {count_time:.2f}s")
        
        # Measure response formation time
        response_start = time.time()
        response = APIResponse(
            status="success",
            data=companies,
            message=f"Found {len(companies)} companies",
            metadata={
                "pagination": {
                    "total": total_count,
                    "page": page,
                    "per_page": limit,
                    "total_pages": (total_count + limit - 1) // limit,
                    "has_next": page * limit < total_count,
                    "has_prev": page > 1
                }
            }
        )
        response_time = time.time() - response_start
        total_time = time.time() - start_time
        
        logging.info(f"[DEBUG] Response formation time: {response_time:.2f}s")
        logging.info(f"[DEBUG] Total request time: {total_time:.2f}s")
        
        return response
        
    except Exception as e:
        logging.error(f"[COMPANIES][SEARCH] Error: {e}")
        logging.error(traceback.format_exc())
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
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results per page"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    db: Session = Depends(get_db)
):
    """
    Get companies by specific location
    
    Args:
        location: Location name (city, region, or area). English names are automatically translated to Russian.
        limit: Maximum number of results per page
        page: Page number (1-based pagination)
        db: Database session
        
    Returns:
        List of companies in the specified location with pagination metadata
    """
    start_time = time.time()
    logging.info(f"[COMPANIES][BY_LOCATION] Request: location={location}, limit={limit}, page={page}")
    try:
        # Calculate offset from page number
        offset = (page - 1) * limit
        logging.info(f"[COMPANIES][BY_LOCATION] Calculated offset={offset} from page={page}, limit={limit}")
        
        company_service = CompanyService(db)
        
        # Measure get_companies_by_location time
        search_start = time.time()
        companies = company_service.get_companies_by_location(location, limit, offset)
        search_time = time.time() - search_start
        logging.info(f"[DEBUG] Get companies by location time: {search_time:.2f}s")
        logging.info(f"[COMPANIES][BY_LOCATION] Found {len(companies)} companies in {location}")
        
        if not companies:
            logging.warning(f"[COMPANIES][BY_LOCATION] No companies found in location: {location}")
            raise HTTPException(
                status_code=404,
                detail=f"No companies found in location: {location}"
            )
        
        # Measure count time
        count_start = time.time()
        total_count = company_service.get_total_company_count_by_location(location)
        count_time = time.time() - count_start
        logging.info(f"[DEBUG] Count by location time: {count_time:.2f}s")
        
        # Measure response formation time
        response_start = time.time()
        response = APIResponse(
            status="success",
            data=companies,
            message=f"Found {len(companies)} companies in {location}",
            metadata={
                "pagination": {
                    "total": total_count,
                    "page": page,
                    "per_page": limit,
                    "total_pages": (total_count + limit - 1) // limit,
                    "has_next": page * limit < total_count,
                    "has_prev": page > 1
                }
            }
        )
        response_time = time.time() - response_start
        total_time = time.time() - start_time
        
        logging.info(f"[DEBUG] Response formation time: {response_time:.2f}s")
        logging.info(f"[DEBUG] Total request time: {total_time:.2f}s")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[COMPANIES][BY_LOCATION] Error: {e}")
        logging.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get companies by location: {str(e)}"
        )


# --- Consideration Endpoints ---
@router.get("/consideration", response_model=List[str], summary="Get user's considered companies")
def get_consideration(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        logging.info(f"[CONSIDERATION] User ID: {current_user.id}")
        logging.info(f"[CONSIDERATION] DB: {db}")
        sql = "SELECT company_bin FROM consideration WHERE user_id = :uid"
        logging.info(f"[CONSIDERATION] Executing SQL: {sql} with uid={str(current_user.id)}")
        rows = db.execute(
            text(sql),
            {"uid": str(current_user.id)}
        ).fetchall()
        result = [row[0] for row in rows]
        logging.info(f"[CONSIDERATION] Result for user_id={current_user.id}: {result}")
        return result
    except Exception as e:
        logging.error(f"[CONSIDERATION] Error for user_id={current_user.id}: {e}")
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch consideration list: {e}")

@router.post("/consideration/{company_bin}", status_code=status.HTTP_201_CREATED, summary="Add company to consideration")
def add_consideration(
    company_bin: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db.execute(
        text("""
        INSERT INTO consideration (user_id, company_bin)
        VALUES (:uid, :bin)
        ON CONFLICT (user_id, company_bin) DO NOTHING
        """),
        {"uid": str(current_user.id), "bin": company_bin}
    )
    db.commit()
    return {"message": "Company added to consideration"}

@router.delete("/consideration/{company_bin}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove company from consideration")
def remove_consideration(
    company_bin: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db.execute(
        text("DELETE FROM consideration WHERE user_id = :uid AND company_bin = :bin"),
        {"uid": str(current_user.id), "bin": company_bin}
    )
    db.commit()
    return


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
    logging.info(f"[COMPANIES][DETAILS] Request: company_id={company_id}")
    try:
        company_service = CompanyService(db)
        company = company_service.get_company_by_id(company_id)  # Removed await
        
        if not company:
            logging.warning(f"[COMPANIES][DETAILS] Company not found: {company_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Company not found with ID: {company_id}"
            )
        logging.info(f"[COMPANIES][DETAILS] Company details retrieved for {company_id}")
            
        return APIResponse(
            status="success",
            data=company,
            message="Company details retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[COMPANIES][DETAILS] Error: {e}")
        logging.error(traceback.format_exc())
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
    logging.info(f"[COMPANIES][LOCATIONS] Request: get all locations")
    try:
        company_service = CompanyService(db)
        locations = company_service.get_all_locations()
        logging.info(f"[COMPANIES][LOCATIONS] Found {len(locations)} locations")
        
        return APIResponse(
            status="success",
            data=locations,
            message=f"Found {len(locations)} locations"
        )
        
    except Exception as e:
        logging.error(f"[COMPANIES][LOCATIONS] Error: {e}")
        logging.error(traceback.format_exc())
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


