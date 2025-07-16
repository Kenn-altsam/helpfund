"""
Service layer for company operations

Business logic for company data retrieval and processing.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from uuid import UUID
import logging

from .models import Company
from ..core.translation_service import CityTranslationService

logging.basicConfig(level=logging.INFO)


class CompanyService:
    """Service class for company operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def search_companies(
        self,
        location: Optional[str] = None,
        company_name: Optional[str] = None,
        activity_keywords: Optional[List[str]] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        logging.info(f"[DB_SERVICE][SEARCH] location={location}, company_name={company_name}, activity_keywords={activity_keywords}, limit={limit}, offset={offset}")
        query = self.db.query(Company)
        filters = []

        # 1. Add location filter if provided
        if location:
            # Translate location to Russian if needed
            translated_location = CityTranslationService.translate_city_name(location)
            # Use ilike for case-insensitive search
            location_filter = Company.locality.ilike(f"%{translated_location}%")
            filters.append(location_filter)
            logging.info(f"[DB_SERVICE][SEARCH] Added location filter: Locality ILIKE '%{translated_location}%' (original input: '{location}')")

        # 2. Add company name filter if provided
        if company_name:
            name_filter = Company.company_name.ilike(f"%{company_name}%")
            filters.append(name_filter)
            logging.info(f"[DB_SERVICE][SEARCH] Added name filter: Company ILIKE '%{company_name}%' ")

        # 3. Add activity filter if provided
        if activity_keywords and len(activity_keywords) > 0:
            activity_filters = []
            for keyword in activity_keywords:
                # Search for each keyword in the activity description
                activity_filters.append(Company.activity.ilike(f"%{keyword}%"))
            # Combine keyword filters with OR (e.g., "строительство" OR "ремонт")
            filters.append(or_(*activity_filters))
            logging.info(f"[DB_SERVICE][SEARCH] Added activity filters for keywords: {activity_keywords}")

        # If we have any filters, apply them with AND
        if filters:
            query = query.filter(and_(*filters))
            logging.info(f"[DB_SERVICE][SEARCH] Applied {len(filters)} filters with AND")
        else:
            logging.warning(f"[DB_SERVICE][SEARCH] No filters applied - will return all companies")

        # --- 4. CRITICAL PAGINATION LOGIC ---
        # Sort by length of tax_data_2025 DESC, then by company name ASC for tie-breaker
        query = query.order_by(func.length(Company.tax_data_2025).desc().nullslast(), Company.company_name.asc())
        logging.info(f"[DB_SERVICE][SEARCH] Applied ORDER BY LENGTH(tax_data_2025) DESC, Company name ASC")

        # Apply the offset to skip previous pages' results, then apply the limit.
        results = query.offset(offset).limit(limit).all()
        logging.info(f"[DB_SERVICE][SEARCH] Applied OFFSET {offset} LIMIT {limit}")
        logging.info(f"[DB_SERVICE][SEARCH] Query executed, returned {len(results)} results")
        
        # --- DEBUG: Log first few results for verification ---
        if results:
            for i, result in enumerate(results[:3]):
                logging.info(f"[DB_SERVICE][SEARCH] Result {i+1}: {result.company_name} (BIN: {result.bin_number})")
            if len(results) > 3:
                logging.info(f"[DB_SERVICE][SEARCH] ... and {len(results) - 3} more")
        else:
            logging.warning(f"[DB_SERVICE][SEARCH] No results returned from database")
        
        # --- END OF PAGINATION LOGIC ---

        # Convert SQLAlchemy objects to dictionaries for the AI service
        converted_results = [self._company_to_dict(c) for c in results]
        return converted_results

    def get_companies_by_location(
        self, 
        location: str, 
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        logging.info(f"[DB_SERVICE][BY_LOCATION] location={location}, limit={limit}, offset={offset}")
        """
        Get companies by specific location
        
        Args:
            location: Location name
            limit: Maximum results
            offset: Number of results to skip
            
        Returns:
            List of company dictionaries
        """
        # Translate location input to Russian if needed
        translated_location = CityTranslationService.translate_city_name(location)
        query = self.db.query(Company).filter(
            Company.locality.ilike(f'%{translated_location}%')
        )
        
        companies = query.order_by(func.length(Company.tax_data_2025).desc().nullslast(), Company.company_name.asc()).offset(offset).limit(limit).all()
        logging.info(f"[DB_SERVICE][BY_LOCATION] Query returned {len(companies)} companies")
        result_dicts = [self._company_to_dict(company) for company in companies]
        return result_dicts

    def get_company_by_id(self, company_id: str) -> Optional[Dict[str, Any]]:
        logging.info(f"[DB_SERVICE][DETAILS] company_id={company_id}")
        """
        Get company by ID
        
        Args:
            company_id: Company BIN
            
        Returns:
            Company dictionary or None
        """
        try:
            company = self.db.query(Company).filter(
                Company.bin_number == company_id
            ).first()
            
            if company:
                logging.info(f"[DB_SERVICE][DETAILS] Company found: {company.company_name} (BIN: {company.bin_number})")
                return self._company_to_dict(company)
            logging.warning(f"[DB_SERVICE][DETAILS] Company not found: {company_id}")
            return None
            
        except Exception as e:
            logging.error(f"[DB_SERVICE][DETAILS] Error: {e}")
            return None

    def get_all_locations(self) -> List[Dict[str, Any]]:
        logging.info(f"[DB_SERVICE][LOCATIONS] Getting all locations with company counts")
        """
        Get all unique locations with company counts
        
        Returns:
            List of location dictionaries with counts
        """
        result = self.db.query(
            Company.locality,
            func.count(Company.bin_number).label('company_count')
        ).group_by(Company.locality).order_by(
            func.count(Company.bin_number).desc()
        ).all()
        logging.info(f"[DB_SERVICE][LOCATIONS] Query returned {len(result)} locations")
        return [
            {
                'location': row.locality,
                'company_count': row.company_count
            }
            for row in result
        ]

    def get_companies_by_region_keywords(
        self, 
        keywords: List[str], 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get companies by region keywords (for AI matching)
        
        Args:
            keywords: List of location keywords
            limit: Maximum results
            
        Returns:
            List of company dictionaries
        """
        query = self.db.query(Company)
        
        # Build OR conditions for each keyword
        conditions = []
        for keyword in keywords:
            conditions.append(Company.locality.ilike(f'%{keyword}%'))
        
        if conditions:
            query = query.filter(or_(*conditions))
        
        companies = query.limit(limit).all()
        return [self._company_to_dict(company) for company in companies]

    def _company_to_dict(self, company: Company) -> Dict[str, Any]:
        """Converts a Company SQLAlchemy object to a dictionary, always including all fields."""
        return {
            "id": getattr(company, "bin_number", None),
            "name": getattr(company, "company_name", "") or "",
            "bin": getattr(company, "bin_number", None),
            "activity": getattr(company, "activity", None),
            "locality": getattr(company, "locality", None),
            "size": getattr(company, "company_size", None),
            "oked": getattr(company, "oked_code", None),
            "kato": getattr(company, "kato_code", None),
            "krp": getattr(company, "krp_code", None),
            "tax_data_2023": getattr(company, "tax_data_2023", None),
            "tax_data_2024": getattr(company, "tax_data_2024", None),
            "tax_data_2025": getattr(company, "tax_data_2025", None),
            "contacts": getattr(company, "contacts", None),
            "website": getattr(company, "website", None),
        }

    def get_total_company_count(self) -> int:
        """Get the total number of companies in the database."""
        return self.db.query(Company).count() 