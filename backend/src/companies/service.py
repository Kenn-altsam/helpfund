"""
Service layer for company operations

Business logic for company data retrieval and processing.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from uuid import UUID

from .models import Company
from ..core.translation_service import CityTranslationService


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
        """
        Searches for companies with flexible filtering and pagination.
        Handles cases where location or activity keywords might be missing.
        """
        print(f"🗃️ [DB_SERVICE] Executing search query:")
        print(f"   location: {location}")
        print(f"   company_name: {company_name}")
        print(f"   activity_keywords: {activity_keywords}")
        print(f"   limit: {limit}")
        print(f"   offset: {offset}")
        
        query = self.db.query(Company)
        filters = []

        # 1. Add location filter if provided
        if location:
            # Translate location to Russian if needed
            translated_location = CityTranslationService.translate_city_name(location)
            # Use ilike for case-insensitive search
            location_filter = Company.locality.ilike(f"%{translated_location}%")
            filters.append(location_filter)
            print(f"🔍 [DB_SERVICE] Added location filter: Locality ILIKE '%{translated_location}%' (original input: '{location}')")

        # 2. Add company name filter if provided
        if company_name:
            name_filter = Company.company_name.ilike(f"%{company_name}%")
            filters.append(name_filter)
            print(f"🔍 [DB_SERVICE] Added name filter: Company ILIKE '%{company_name}%'")

        # 3. Add activity filter if provided
        if activity_keywords and len(activity_keywords) > 0:
            activity_filters = []
            for keyword in activity_keywords:
                # Search for each keyword in the activity description
                activity_filters.append(Company.activity.ilike(f"%{keyword}%"))
            # Combine keyword filters with OR (e.g., "строительство" OR "ремонт")
            filters.append(or_(*activity_filters))
            print(f"🔍 [DB_SERVICE] Added activity filters for keywords: {activity_keywords}")

        # If we have any filters, apply them with AND
        if filters:
            query = query.filter(and_(*filters))
            print(f"🔍 [DB_SERVICE] Applied {len(filters)} filters with AND")
        else:
            print(f"⚠️ [DB_SERVICE] No filters applied - will return all companies")

        # --- 4. CRITICAL PAGINATION LOGIC ---
        # A consistent order is REQUIRED for pagination (OFFSET) to work reliably.
        # We order by company name to ensure the same query always returns results
        # in the same sequence. Your model uses 'Company' for the name column.
        query = query.order_by(Company.company_name.asc())
        print(f"🔄 [DB_SERVICE] Applied ORDER BY Company name ASC")

        # Apply the offset to skip previous pages' results, then apply the limit.
        results = query.offset(offset).limit(limit).all()
        print(f"📊 [DB_SERVICE] Applied OFFSET {offset} LIMIT {limit}")
        print(f"✅ [DB_SERVICE] Query executed, returned {len(results)} results")
        
        # --- DEBUG: Log first few results for verification ---
        if results:
            print(f"🏢 [DB_SERVICE] First few results:")
            for i, result in enumerate(results[:3]):
                print(f"   {i+1}. {result.company_name} (BIN: {result.bin_number})")
            if len(results) > 3:
                print(f"   ... and {len(results) - 3} more")
        else:
            print(f"⚠️ [DB_SERVICE] No results returned from database")
        
        # --- END OF PAGINATION LOGIC ---

        # Convert SQLAlchemy objects to dictionaries for the AI service
        converted_results = [self._company_to_dict(c) for c in results]
        print(f"🔄 [DB_SERVICE] Converted {len(converted_results)} results to dictionaries")
        return converted_results

    def get_companies_by_location(
        self, 
        location: str, 
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
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
        
        companies = query.order_by(Company.company_name.asc()).offset(offset).limit(limit).all()
        return [self._company_to_dict(company) for company in companies]

    def get_company_by_id(self, company_id: str) -> Optional[Dict[str, Any]]:
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
                return self._company_to_dict(company)
            return None
            
        except Exception:
            return None

    def get_all_locations(self) -> List[Dict[str, Any]]:
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
        """Converts a Company SQLAlchemy object to a dictionary."""
        return {
            "id": company.bin_number,
            "name": company.company_name or "",
            "bin": company.bin_number,
            "activity": company.activity,
            "locality": company.locality,
            "size": company.company_size,
            "oked": company.oked_code,
            "kato": company.kato_code,
            "krp": company.krp_code,
            "tax_data_2023": company.tax_data_2023,
            "tax_data_2024": company.tax_data_2024,
            "tax_data_2025": company.tax_data_2025,
            "contacts": {
                "phone": company.phone,
                "email": company.email
            },
            "website": company.website,
        }

    def get_total_company_count(self) -> int:
        """Get the total number of companies in the database."""
        return self.db.query(Company).count() 