"""
Service layer for company operations

Business logic for company data retrieval and processing.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from uuid import UUID
import asyncio

from .models import Company
from ..core.translation_service import CityTranslationService


class CompanyService:
    """Service class for company operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def search_companies(
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
        # Run the synchronous DB query in an async-compatible way
        return await asyncio.to_thread(
            self._execute_search_query, 
            location, 
            company_name, 
            activity_keywords, 
            limit, 
            offset
        )

    def _execute_search_query(
        self,
        location: Optional[str],
        company_name: Optional[str],
        activity_keywords: Optional[List[str]],
        limit: int,
        offset: int
    ) -> List[Dict[str, Any]]:
        
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
            # Use ilike for case-insensitive search
            location_filter = Company.Locality.ilike(f"%{location}%")
            filters.append(location_filter)
            print(f"🔍 [DB_SERVICE] Added location filter: Locality ILIKE '%{location}%'")

        # 2. Add company name filter if provided
        if company_name:
            name_filter = Company.Company.ilike(f"%{company_name}%")
            filters.append(name_filter)
            print(f"🔍 [DB_SERVICE] Added name filter: Company ILIKE '%{company_name}%'")

        # 3. Add activity filter if provided
        if activity_keywords and len(activity_keywords) > 0:
            activity_filters = []
            for keyword in activity_keywords:
                # Search for each keyword in the activity description
                activity_filters.append(Company.Activity.ilike(f"%{keyword}%"))
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
        query = query.order_by(Company.Company)
        print(f"🔄 [DB_SERVICE] Applied ORDER BY Company (company name)")

        # Apply the offset to skip previous pages' results, then apply the limit.
        results = query.offset(offset).limit(limit).all()
        print(f"📊 [DB_SERVICE] Applied OFFSET {offset} LIMIT {limit}")
        print(f"✅ [DB_SERVICE] Query executed, returned {len(results)} results")
        
        # --- DEBUG: Log first few results for verification ---
        if results:
            print(f"🏢 [DB_SERVICE] First few results:")
            for i, result in enumerate(results[:3]):
                print(f"   {i+1}. {result.Company} (BIN: {result.BIN})")
            if len(results) > 3:
                print(f"   ... and {len(results) - 3} more")
        else:
            print(f"⚠️ [DB_SERVICE] No results returned from database")
        
        # --- END OF PAGINATION LOGIC ---

        # Convert SQLAlchemy objects to dictionaries for the AI service
        converted_results = [self._company_to_dict(c) for c in results]
        print(f"🔄 [DB_SERVICE] Converted {len(converted_results)} results to dictionaries")
        return converted_results

    async def get_companies_by_location(
        self, 
        location: str, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get companies by specific location
        
        Args:
            location: Location name
            limit: Maximum results
            
        Returns:
            List of company dictionaries
        """
        return await asyncio.to_thread(
            self._execute_location_query, location, limit
        )

    def _execute_location_query(self, location: str, limit: int) -> List[Dict[str, Any]]:
        """Execute location-based query synchronously"""
        query = self.db.query(Company).filter(
            Company.Locality.ilike(f'%{location}%')
        )
        
        companies = query.limit(limit).all()
        return [self._company_to_dict(company) for company in companies]

    async def get_company_by_id(self, company_id: str) -> Optional[Dict[str, Any]]:
        """
        Get company by ID
        
        Args:
            company_id: Company UUID
            
        Returns:
            Company dictionary or None
        """
        return await asyncio.to_thread(self._get_company_by_id_sync, company_id)

    def _get_company_by_id_sync(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Get company by ID synchronously"""
        try:
            company = self.db.query(Company).filter(
                Company.id == company_id
            ).first()
            
            if company:
                return self._company_to_dict(company)
            return None
            
        except Exception:
            return None

    async def get_all_locations(self) -> List[Dict[str, Any]]:
        """
        Get all unique locations with company counts
        
        Returns:
            List of location dictionaries with counts
        """
        return await asyncio.to_thread(self._get_all_locations_sync)

    def _get_all_locations_sync(self) -> List[Dict[str, Any]]:
        """Get all locations synchronously"""
        from sqlalchemy import func
        
        result = self.db.query(
            Company.Locality,
            func.count(Company.id).label('company_count')
        ).group_by(Company.Locality).order_by(
            func.count(Company.id).desc()
        ).all()
        
        return [
            {
                'location': row.Locality,
                'company_count': row.company_count
            }
            for row in result
        ]

    async def get_companies_by_region_keywords(
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
        return await asyncio.to_thread(
            self._get_companies_by_keywords_sync, keywords, limit
        )

    def _get_companies_by_keywords_sync(
        self, keywords: List[str], limit: int
    ) -> List[Dict[str, Any]]:
        """Get companies by keywords synchronously"""
        query = self.db.query(Company)
        
        # Build OR conditions for each keyword
        conditions = []
        for keyword in keywords:
            conditions.append(Company.Locality.ilike(f'%{keyword}%'))
        
        if conditions:
            query = query.filter(or_(*conditions))
        
        companies = query.limit(limit).all()
        return [self._company_to_dict(company) for company in companies]

    def _company_to_dict(self, company: Company) -> Dict[str, Any]:
        """Converts a Company SQLAlchemy object to a dictionary."""
        # FIX: Use the correct capitalized attribute names from the SQLAlchemy model
        # (e.g., company.BIN) and map them to lowercase snake_case keys for the API.
        return {
            "id": str(company.id),
            "bin": company.BIN,
            "name": company.Company,
            "oked": company.OKED,
            "activity": company.Activity,
            "kato": company.KATO,
            "locality": company.Locality,
            "krp": company.KRP,
            "size": company.Size,

            # Tax information (may be missing if the DB wasn't migrated yet)
            "annual_tax_paid": getattr(company, "annual_tax_paid", None),
            "tax_2020": getattr(company, "tax_2020", None),
            "tax_2021": getattr(company, "tax_2021", None),
            "tax_2022": getattr(company, "tax_2022", None),
            "tax_2023": getattr(company, "tax_2023", None),
            "tax_2024": getattr(company, "tax_2024", None),
            "tax_2025": getattr(company, "tax_2025", None),
            "last_tax_update": getattr(company, "last_tax_update", None).isoformat() if getattr(company, "last_tax_update", None) else None,
        } 