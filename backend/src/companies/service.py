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
    
    def test_offset_functionality(self, location: str = "Алматы") -> Dict[str, Any]:
        """
        Test function to verify that offset is working correctly.
        This will run the same query with different offsets to see if we get different results.
        """
        logging.info(f"[DB_SERVICE][TEST_OFFSET] Testing offset functionality for location: {location}")
        
        # Test with offset 0
        results_0 = self.search_companies(location=location, limit=5, offset=0)
        first_companies_0 = [r['name'] for r in results_0[:3]]
        
        # Test with offset 5
        results_5 = self.search_companies(location=location, limit=5, offset=5)
        first_companies_5 = [r['name'] for r in results_5[:3]]
        
        # Test with offset 10
        results_10 = self.search_companies(location=location, limit=5, offset=10)
        first_companies_10 = [r['name'] for r in results_10[:3]]
        
        logging.info(f"[DB_SERVICE][TEST_OFFSET] Offset 0 results: {first_companies_0}")
        logging.info(f"[DB_SERVICE][TEST_OFFSET] Offset 5 results: {first_companies_5}")
        logging.info(f"[DB_SERVICE][TEST_OFFSET] Offset 10 results: {first_companies_10}")
        
        # Check if results are different
        offset_0_5_different = set(first_companies_0) != set(first_companies_5)
        offset_5_10_different = set(first_companies_5) != set(first_companies_10)
        
        logging.info(f"[DB_SERVICE][TEST_OFFSET] Offset 0 vs 5 different: {offset_0_5_different}")
        logging.info(f"[DB_SERVICE][TEST_OFFSET] Offset 5 vs 10 different: {offset_5_10_different}")
        
        return {
            "offset_0_results": first_companies_0,
            "offset_5_results": first_companies_5,
            "offset_10_results": first_companies_10,
            "offset_0_5_different": offset_0_5_different,
            "offset_5_10_different": offset_5_10_different,
            "offset_working": offset_0_5_different and offset_5_10_different
        }

    def search_companies(
        self,
        location: Optional[str] = None,
        company_name: Optional[str] = None,
        activity_keywords: Optional[List[str]] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        logging.info(f"[DB_SERVICE][SEARCH] location={location}, company_name={company_name}, activity_keywords={activity_keywords}, limit={limit}, offset={offset}")
        
        # Optimized query construction - only select needed columns for better performance
        query_parts = [
            "SELECT id, \"Company\", \"BIN\", \"Activity\", \"Locality\", \"OKED\", \"Size\", \"KATO\", \"KRP\", tax_data_2023, tax_data_2024, tax_data_2025",
            "FROM companies WHERE 1=1"
        ]
        params = {}
        param_count = 0
        
        # 1. Add location filter if provided (using indexed column)
        if location:
            translated_location = CityTranslationService.translate_city_name(location)
            param_count += 1
            query_parts.append(f"AND \"Locality\" ILIKE :loc_{param_count}")
            params[f"loc_{param_count}"] = f"%{translated_location}%"
            logging.info(f"[DB_SERVICE][SEARCH] Added location filter: Locality ILIKE '%{translated_location}%'")

        # 2. Add company name filter if provided (optimized for single word vs multi-word)
        if company_name:
            if len(company_name.split()) > 1:
                # Use full-text search for multi-word queries (faster than ILIKE)
                param_count += 1
                query_parts.append(f"AND to_tsvector('russian', \"Company\") @@ plainto_tsquery('russian', :name_{param_count})")
                params[f"name_{param_count}"] = company_name
                logging.info(f"[DB_SERVICE][SEARCH] Added full-text name filter for: {company_name}")
            else:
                # Use ILIKE for single word queries (faster for simple patterns)
                param_count += 1
                query_parts.append(f"AND \"Company\" ILIKE :name_{param_count}")
                params[f"name_{param_count}"] = f"%{company_name}%"
                logging.info(f"[DB_SERVICE][SEARCH] Added ILIKE name filter: Company ILIKE '%{company_name}%'")

        # 3. Add activity filter if provided (optimized full-text search)
        if activity_keywords and len(activity_keywords) > 0:
            if len(activity_keywords) == 1:
                # Single keyword - use ILIKE for better performance
                param_count += 1
                query_parts.append(f"AND \"Activity\" ILIKE :act_{param_count}")
                params[f"act_{param_count}"] = f"%{activity_keywords[0]}%"
                logging.info(f"[DB_SERVICE][SEARCH] Added ILIKE activity filter: Activity ILIKE '%{activity_keywords[0]}%'")
            else:
                # Multiple keywords - use full-text search
                activity_conditions = []
                for i, keyword in enumerate(activity_keywords):
                    param_count += 1
                    activity_conditions.append(f"to_tsvector('russian', \"Activity\") @@ plainto_tsquery('russian', :act_{param_count})")
                    params[f"act_{param_count}"] = keyword
                query_parts.append(f"AND ({' OR '.join(activity_conditions)})")
                logging.info(f"[DB_SERVICE][SEARCH] Added full-text activity filters for keywords: {activity_keywords}")

        # 4. Optimized ORDER BY - use indexed columns first, then expensive operations
        # Start with indexed columns for better performance
        query_parts.append("ORDER BY \"Locality\" ASC, COALESCE(tax_data_2025, 0) DESC, \"Company\" ASC")
        logging.info(f"[DB_SERVICE][SEARCH] Applied optimized ORDER BY")

        # 5. Add pagination - ALWAYS use both LIMIT and OFFSET
        query_parts.append("LIMIT :limit OFFSET :offset")
        params["limit"] = limit
        params["offset"] = offset
        logging.info(f"[DB_SERVICE][SEARCH] Applied LIMIT {limit} OFFSET {offset}")
        
        # Execute the optimized query
        final_query = " ".join(query_parts)
        logging.info(f"[DB_SERVICE][SEARCH] Final query: {final_query}")
        logging.info(f"[DB_SERVICE][SEARCH] Parameters: {params}")
        
        try:
            # Ensure we start with a clean transaction state
            self.db.rollback()
            
            # Execute the main query directly - no need for test query
            result = self.db.execute(text(final_query), params)
            results = result.fetchall()
            logging.info(f"[DB_SERVICE][SEARCH] Query executed, returned {len(results)} results")
            
            # Convert results to dictionaries efficiently
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
                    "contacts": None,  # phone and email columns don't exist in actual database
                    "website": None,   # location column doesn't exist in actual DB
                }
                converted_results.append(company_dict)
            
            # Minimal debug logging for performance
            if converted_results:
                logging.info(f"[DB_SERVICE][SEARCH] First result: {converted_results[0]['name']} (BIN: {converted_results[0]['bin']})")
                if len(converted_results) > 1:
                    logging.info(f"[DB_SERVICE][SEARCH] Second result: {converted_results[1]['name']} (BIN: {converted_results[1]['bin']})")
                if len(converted_results) > 2:
                    logging.info(f"[DB_SERVICE][SEARCH] Third result: {converted_results[2]['name']} (BIN: {converted_results[2]['bin']})")
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
        
        try:
            # Ensure we start with a clean transaction state
            self.db.rollback()
            
            # Use select() for better performance - only select needed columns
            from sqlalchemy import select
            query = select(Company.id, Company.company_name, Company.bin_number, Company.activity, 
                          Company.locality, Company.oked_code, Company.company_size, Company.kato_code, 
                          Company.krp_code, Company.tax_data_2023, Company.tax_data_2024, Company.tax_data_2025)
            filters = []

            if location:
                translated_location = CityTranslationService.translate_city_name(location)
                location_filter = Company.locality.ilike(f"%{translated_location}%")
                filters.append(location_filter)

            if company_name:
                name_filter = Company.company_name.ilike(f"%{company_name}%")
                filters.append(name_filter)

            if activity_keywords and len(activity_keywords) > 0:
                if len(activity_keywords) == 1:
                    # Single keyword - use ILIKE for better performance
                    activity_filter = Company.activity.ilike(f"%{activity_keywords[0]}%")
                    filters.append(activity_filter)
                else:
                    # Multiple keywords - use OR conditions
                    activity_filters = []
                    for keyword in activity_keywords:
                        activity_filters.append(Company.activity.ilike(f"%{keyword}%"))
                    filters.append(or_(*activity_filters))

            if filters:
                query = query.where(and_(*filters))

            # Optimized ORDER BY - use indexed columns first
            query = query.order_by(
                Company.locality.asc(),
                func.coalesce(Company.tax_data_2025, 0).desc().nullslast(), 
                Company.company_name.asc()
            ).offset(offset).limit(limit)
            
            result = self.db.execute(query)
            rows = result.fetchall()
            
            # Convert to dictionaries efficiently
            converted_results = []
            for row in rows:
                company_dict = {
                    "id": row.id,
                    "name": row.company_name,
                    "bin": row.bin_number,
                    "activity": row.activity,
                    "locality": row.locality,
                    "oked": row.oked_code,
                    "size": row.company_size,
                    "kato": row.kato_code,
                    "krp": row.krp_code,
                    "tax_data_2023": row.tax_data_2023,
                    "tax_data_2024": row.tax_data_2024,
                    "tax_data_2025": row.tax_data_2025,
                    "contacts": None,
                    "website": None,
                }
                converted_results.append(company_dict)
            
            return converted_results
            
        except Exception as e:
            logging.error(f"[DB_SERVICE][FALLBACK] Error in fallback search: {e}")
            # Return empty list if even fallback fails
            return []

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
        # Use optimized query with proper indexing - only select needed columns
        translated_location = CityTranslationService.translate_city_name(location)
        
        query = """
            SELECT id, "Company", "BIN", "Activity", "Locality", "OKED", "Size", "KATO", "KRP", tax_data_2023, tax_data_2024, tax_data_2025
            FROM companies 
            WHERE "Locality" ILIKE :location
            ORDER BY "Locality" ASC, COALESCE(tax_data_2025, 0) DESC, "Company" ASC
            LIMIT :limit OFFSET :offset
        """
        
        try:
            # Ensure we start with a clean transaction state
            self.db.rollback()
            
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
                    "tax_data_2023": row.tax_data_2023,
                    "tax_data_2024": row.tax_data_2024,
                    "tax_data_2025": row.tax_data_2025,
                    "contacts": None,  # phone and email columns don't exist in actual database
                    "website": None,   # location column doesn't exist in actual DB
                }
                result_dicts.append(company_dict)
            
            return result_dicts
            
        except Exception as e:
            logging.error(f"[DB_SERVICE][BY_LOCATION] Error: {e}")
            # Fallback to ORM
            try:
                self.db.rollback()
                query = self.db.query(Company).filter(
                    Company.locality.ilike(f'%{translated_location}%')
                )
                companies = query.order_by(
                    Company.locality.asc(),
                    func.coalesce(Company.tax_data_2025, 0).desc().nullslast(), 
                    Company.company_name.asc()
                ).offset(offset).limit(limit).all()
                return [self._company_to_dict(company) for company in companies]
            except Exception as orm_error:
                logging.error(f"[DB_SERVICE][BY_LOCATION] ORM fallback also failed: {orm_error}")
                return []

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
            # Ensure we start with a clean transaction state
            self.db.rollback()
            
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
        try:
            # Ensure we start with a clean transaction state
            self.db.rollback()
            
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
        except Exception as e:
            logging.error(f"[DB_SERVICE][LOCATIONS] Error: {e}")
            return []

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
        try:
            # Ensure we start with a clean transaction state
            self.db.rollback()
            
            # Use select() for better performance - only select needed columns
            from sqlalchemy import select
            query = select(Company.id, Company.company_name, Company.bin_number, Company.activity, 
                          Company.locality, Company.oked_code, Company.company_size, Company.kato_code, 
                          Company.krp_code, Company.tax_data_2023, Company.tax_data_2024, Company.tax_data_2025)
            
            # Build OR conditions for each keyword
            conditions = []
            for keyword in keywords:
                conditions.append(Company.locality.ilike(f'%{keyword}%'))
            
            if conditions:
                query = query.where(or_(*conditions))
            
            # Optimized ORDER BY - use indexed columns first
            query = query.order_by(
                Company.locality.asc(),
                func.coalesce(Company.tax_data_2025, 0).desc().nullslast(), 
                Company.company_name.asc()
            ).limit(limit)
            
            result = self.db.execute(query)
            rows = result.fetchall()
            
            # Convert to dictionaries efficiently
            converted_results = []
            for row in rows:
                company_dict = {
                    "id": row.id,
                    "name": row.company_name,
                    "bin": row.bin_number,
                    "activity": row.activity,
                    "locality": row.locality,
                    "oked": row.oked_code,
                    "size": row.company_size,
                    "kato": row.kato_code,
                    "krp": row.krp_code,
                    "tax_data_2023": row.tax_data_2023,
                    "tax_data_2024": row.tax_data_2024,
                    "tax_data_2025": row.tax_data_2025,
                    "contacts": None,
                    "website": None,
                }
                converted_results.append(company_dict)
            
            return converted_results
            
        except Exception as e:
            logging.error(f"[DB_SERVICE][REGION_KEYWORDS] Error: {e}")
            return []

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
            "tax_data_2023": getattr(company, "tax_data_2023", None),
            "tax_data_2024": getattr(company, "tax_data_2024", None),
            "tax_data_2025": getattr(company, "tax_data_2025", None),
            "contacts": None,  # phone and email columns don't exist in actual database
            "website": None,   # location column doesn't exist in actual DB
        }

    def get_total_company_count(self) -> int:
        """Get the total number of companies in the database."""
        try:
            # Ensure we start with a clean transaction state
            self.db.rollback()
            return self.db.query(Company).count()
        except Exception as e:
            logging.error(f"[DB_SERVICE][COUNT] Error: {e}")
            return 0 