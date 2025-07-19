"""
Service layer for company operations

Business logic for company data retrieval and processing.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, text
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
        
        # Use raw SQL for optimal performance with proper indexing
        query_parts = ["SELECT * FROM companies WHERE 1=1"]
        params = {}
        param_count = 0
        
        # 1. Add location filter if provided (using indexed column)
        if location:
            translated_location = CityTranslationService.translate_city_name(location)
            param_count += 1
            query_parts.append(f"AND \"Locality\" ILIKE :loc_{param_count}")
            params[f"loc_{param_count}"] = f"%{translated_location}%"
            logging.info(f"[DB_SERVICE][SEARCH] Added location filter: Locality ILIKE '%{translated_location}%'")

        # 2. Add company name filter if provided (using full-text search when possible)
        if company_name:
            if len(company_name.split()) > 1:
                # Use full-text search for multi-word queries
                param_count += 1
                query_parts.append(f"AND to_tsvector('russian', \"Company\") @@ plainto_tsquery('russian', :name_{param_count})")
                params[f"name_{param_count}"] = company_name
                logging.info(f"[DB_SERVICE][SEARCH] Added full-text name filter for: {company_name}")
            else:
                # Use ILIKE for single word queries
                param_count += 1
                query_parts.append(f"AND \"Company\" ILIKE :name_{param_count}")
                params[f"name_{param_count}"] = f"%{company_name}%"
                logging.info(f"[DB_SERVICE][SEARCH] Added ILIKE name filter: Company ILIKE '%{company_name}%'")

        # 3. Add activity filter if provided (using full-text search)
        if activity_keywords and len(activity_keywords) > 0:
            activity_conditions = []
            for i, keyword in enumerate(activity_keywords):
                param_count += 1
                activity_conditions.append(f"to_tsvector('russian', \"Activity\") @@ plainto_tsquery('russian', :act_{param_count})")
                params[f"act_{param_count}"] = keyword
            query_parts.append(f"AND ({' OR '.join(activity_conditions)})")
            logging.info(f"[DB_SERVICE][SEARCH] Added activity filters for keywords: {activity_keywords}")

        # 4. Optimized ORDER BY using indexed numeric column instead of string length
        # Using tax_data_2025 as per actual database schema
        query_parts.append("ORDER BY COALESCE(tax_data_2025, 0) DESC, \"Company\" ASC")
        logging.info(f"[DB_SERVICE][SEARCH] Applied ORDER BY tax_data_2025 DESC, Company ASC")

        # 5. Add pagination
        query_parts.append("LIMIT :limit OFFSET :offset")
        params["limit"] = limit
        params["offset"] = offset
        logging.info(f"[DB_SERVICE][SEARCH] Applied LIMIT {limit} OFFSET {offset}")
        
        # Execute the optimized query
        final_query = " ".join(query_parts)
        logging.info(f"[DB_SERVICE][SEARCH] Final query: {final_query}")
        
        try:
            result = self.db.execute(text(final_query), params)
            results = result.fetchall()
            logging.info(f"[DB_SERVICE][SEARCH] Query executed, returned {len(results)} results")
            
            # Convert results to dictionaries
            converted_results = []
            for row in results:
                company_dict = {
                    "id": row.id,
                    "name": row.Company,
                    "bin": row.BIN,
                    "activity": row.Activity,
                    "locality": row.Locality,
                    "oked": row.OKED,
                    "size": row.Size,
                    "kato": row.KATO,
                    "krp": row.KRP,
                    "tax_data_2023": row.tax_data_2023,
                    "tax_data_2024": row.tax_data_2024,
                    "tax_data_2025": row.tax_data_2025,
                    "contacts": row.phone or row.email,
                    "website": row.location,  # Using location field as website for now
                }
                converted_results.append(company_dict)
            
            # Debug logging
            if converted_results:
                for i, result in enumerate(converted_results[:3]):
                    logging.info(f"[DB_SERVICE][SEARCH] Result {i+1}: {result['name']} (BIN: {result['bin']})")
                if len(converted_results) > 3:
                    logging.info(f"[DB_SERVICE][SEARCH] ... and {len(converted_results) - 3} more")
            else:
                logging.warning(f"[DB_SERVICE][SEARCH] No results returned from database")
            
            return converted_results
            
        except Exception as e:
            logging.error(f"[DB_SERVICE][SEARCH] Database error: {e}")
            # Fallback to SQLAlchemy ORM if raw SQL fails
            return self._fallback_search(location, company_name, activity_keywords, limit, offset)

    def _fallback_search(
        self,
        location: Optional[str] = None,
        company_name: Optional[str] = None,
        activity_keywords: Optional[List[str]] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Fallback search using SQLAlchemy ORM if raw SQL fails"""
        logging.info(f"[DB_SERVICE][FALLBACK] Using ORM fallback search")
        query = self.db.query(Company)
        filters = []

        if location:
            translated_location = CityTranslationService.translate_city_name(location)
            location_filter = Company.locality.ilike(f"%{translated_location}%")
            filters.append(location_filter)

        if company_name:
            name_filter = Company.company_name.ilike(f"%{company_name}%")
            filters.append(name_filter)

        if activity_keywords and len(activity_keywords) > 0:
            activity_filters = []
            for keyword in activity_keywords:
                activity_filters.append(Company.activity.ilike(f"%{keyword}%"))
            filters.append(or_(*activity_filters))

        if filters:
            query = query.filter(and_(*filters))

        # Use tax_data_2025 for sorting (as per actual database schema)
        query = query.order_by(
            func.coalesce(Company.tax_data_2025, 0).desc().nullslast(), 
            Company.company_name.asc()
        )
        results = query.offset(offset).limit(limit).all()
        
        return [self._company_to_dict(c) for c in results]

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
        # Use optimized query with proper indexing
        translated_location = CityTranslationService.translate_city_name(location)
        
        query = """
            SELECT * FROM companies 
            WHERE "Locality" ILIKE :location
            ORDER BY COALESCE(tax_data_2025, 0) DESC, "Company" ASC
            LIMIT :limit OFFSET :offset
        """
        
        try:
            result = self.db.execute(text(query), {
                "location": f"%{translated_location}%",
                "limit": limit,
                "offset": offset
            })
            companies = result.fetchall()
            logging.info(f"[DB_SERVICE][BY_LOCATION] Query returned {len(companies)} companies")
            
            result_dicts = []
            for row in companies:
                company_dict = {
                    "id": row.id,
                    "name": row.Company,
                    "bin": row.BIN,
                    "activity": row.Activity,
                    "locality": row.Locality,
                    "oked": row.OKED,
                    "size": row.Size,
                    "kato": row.KATO,
                    "krp": row.KRP,
                    "tax_data_2023": row.tax_payment_2023,
                    "tax_data_2024": row.tax_payment_2024,
                    "tax_data_2025": row.tax_payment_2025,
                    "contacts": row.phone or row.email,
                    "website": row.location,
                }
                result_dicts.append(company_dict)
            
            return result_dicts
            
        except Exception as e:
            logging.error(f"[DB_SERVICE][BY_LOCATION] Error: {e}")
            # Fallback to ORM
            query = self.db.query(Company).filter(
                Company.locality.ilike(f'%{translated_location}%')
            )
            companies = query.order_by(
                func.coalesce(Company.tax_payment_2025, 0).desc().nullslast(), 
                Company.company_name.asc()
            ).offset(offset).limit(limit).all()
            return [self._company_to_dict(company) for company in companies]

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
            "id": getattr(company, "id", None),
            "name": getattr(company, "company_name", "") or "",
            "bin": getattr(company, "bin_number", None),
            "activity": getattr(company, "activity", None),
            "locality": getattr(company, "locality", None),
            "size": getattr(company, "company_size", None),
            "oked": getattr(company, "oked_code", None),
            "kato": getattr(company, "kato_code", None),
            "krp": getattr(company, "krp_code", None),
            "tax_data_2023": getattr(company, "tax_payment_2023", None),
            "tax_data_2024": getattr(company, "tax_payment_2024", None),
            "tax_data_2025": getattr(company, "tax_payment_2025", None),
            "contacts": getattr(company, "phone", None) or getattr(company, "email", None),
            "website": getattr(company, "location", None),
        }

    def get_total_company_count(self) -> int:
        """Get the total number of companies in the database."""
        return self.db.query(Company).count() 