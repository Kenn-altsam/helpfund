"""
Google Search Service for Company Information

Provides functionality to search for company websites and contact information
using Google Custom Search API.
"""

import asyncio
import logging
import re
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
import httpx
import os
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)


@dataclass
class CompanyWebInfo:
    """Data class for company web information"""
    website: Optional[str] = None
    contacts: Optional[str] = None
    confidence_score: float = 0.0
    search_query: str = ""


class GoogleSearchService:
    """Service for searching company information using Google Custom Search API"""
    
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.search_engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        
        if not self.api_key or not self.search_engine_id:
            logging.warning("[GOOGLE_SEARCH] API credentials not configured")
    
    def _is_valid_config(self) -> bool:
        """Check if Google Search API is properly configured"""
        return bool(self.api_key and self.search_engine_id)
    
    async def search_company_info(
        self, 
        company_name: str, 
        company_bin: Optional[str] = None,
        location: Optional[str] = None
    ) -> CompanyWebInfo:
        """
        Search for company website and contact information
        
        Args:
            company_name: Name of the company
            company_bin: BIN number of the company
            location: Company location for better search accuracy
            
        Returns:
            CompanyWebInfo object with found information
        """
        if not self._is_valid_config():
            logging.warning("[GOOGLE_SEARCH] API not configured, returning empty results")
            return CompanyWebInfo()
        
        # Build search query
        search_query = self._build_search_query(company_name, company_bin, location)
        
        try:
            # Perform search
            search_results = await self._perform_search(search_query)
            
            # Extract information from results
            web_info = self._extract_company_info(search_results, company_name)
            web_info.search_query = search_query
            
            logging.info(f"[GOOGLE_SEARCH] Found info for '{company_name}': website={web_info.website}, contacts={bool(web_info.contacts)}")
            return web_info
            
        except Exception as e:
            logging.error(f"[GOOGLE_SEARCH] Error searching for '{company_name}': {e}")
            return CompanyWebInfo(search_query=search_query)
    
    def _build_search_query(
        self, 
        company_name: str, 
        company_bin: Optional[str] = None,
        location: Optional[str] = None
    ) -> str:
        """Build optimized search query for the company"""
        # Clean company name
        clean_name = self._clean_company_name(company_name)
        
        # Base query with company name
        query_parts = [f'"{clean_name}"']
        
        # Add Kazakhstan context
        query_parts.append("Казахстан OR Kazakhstan")
        
        # Add BIN if available
        if company_bin:
            query_parts.append(f"БИН {company_bin}")
        
        # Add location if available
        if location:
            query_parts.append(f'"{location}"')
        
        # Add terms to find official websites
        query_parts.append("сайт OR website OR контакты OR contacts")
        
        return " ".join(query_parts)
    
    def _clean_company_name(self, company_name: str) -> str:
        """Clean company name for better search results"""
        # Remove common company suffixes that might interfere with search
        suffixes_to_remove = [
            r'\bТОО\b', r'\bАО\b', r'\bЖШС\b', r'\bТ\.О\.О\b', r'\bА\.О\b',
            r'\bLLC\b', r'\bLTD\b', r'\bINC\b', r'\bCORP\b', r'\bLIMITED\b'
        ]
        
        cleaned = company_name
        for suffix in suffixes_to_remove:
            cleaned = re.sub(suffix, '', cleaned, flags=re.IGNORECASE)
        
        return cleaned.strip()
    
    async def _perform_search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """Perform Google Custom Search API request"""
        params = {
            'key': self.api_key,
            'cx': self.search_engine_id,
            'q': query,
            'num': num_results,
            'fields': 'items(title,link,snippet,displayLink)',
            'hl': 'ru',  # Results in Russian
            'lr': 'lang_ru|lang_kk|lang_en'  # Languages: Russian, Kazakh, English
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            return data.get('items', [])
    
    def _extract_company_info(self, search_results: List[Dict[str, Any]], company_name: str) -> CompanyWebInfo:
        """Extract website and contact information from search results"""
        websites = []
        contacts = []
        confidence_scores = []
        
        for result in search_results:
            title = result.get('title', '')
            link = result.get('link', '')
            snippet = result.get('snippet', '')
            display_link = result.get('displayLink', '')
            
            # Calculate relevance score
            relevance = self._calculate_relevance(title, snippet, company_name)
            confidence_scores.append(relevance)
            
            # Extract website
            if self._is_likely_company_website(link, display_link, title, company_name):
                websites.append((link, relevance))
            
            # Extract contacts from snippet
            contact_info = self._extract_contacts_from_text(snippet)
            if contact_info:
                contacts.append((contact_info, relevance))
        
        # Select best website
        best_website = None
        if websites:
            # Sort by relevance and pick the best one
            websites.sort(key=lambda x: x[1], reverse=True)
            best_website = websites[0][0]
        
        # Combine contact information
        best_contacts = None
        if contacts:
            # Sort by relevance and combine top contacts
            contacts.sort(key=lambda x: x[1], reverse=True)
            # Take top 2 most relevant contact entries
            top_contacts = [contact[0] for contact in contacts[:2]]
            best_contacts = " | ".join(top_contacts)
        
        # Overall confidence score
        confidence = max(confidence_scores) if confidence_scores else 0.0
        
        return CompanyWebInfo(
            website=best_website,
            contacts=best_contacts,
            confidence_score=confidence
        )
    
    def _is_likely_company_website(
        self, 
        link: str, 
        display_link: str, 
        title: str, 
        company_name: str
    ) -> bool:
        """Determine if a link is likely the company's official website"""
        # Skip social media and directory sites
        excluded_domains = [
            'facebook.com', 'instagram.com', 'linkedin.com', 'twitter.com',
            'vk.com', 'ok.ru', 'youtube.com', 'telegram.org',
            'google.com', 'yandex.kz', 'yandex.ru', 'mail.ru',
            'wikipedia.org', 'wiki', 'directory', 'catalog'
        ]
        
        domain = urlparse(link).netloc.lower()
        
        for excluded in excluded_domains:
            if excluded in domain:
                return False
        
        # Prefer domains that might be related to the company
        company_words = self._clean_company_name(company_name).lower().split()
        for word in company_words:
            if len(word) > 3 and word in domain:
                return True
        
        # Check if title contains company name
        if any(word in title.lower() for word in company_words if len(word) > 3):
            return True
        
        return True  # Default to true if no exclusions apply
    
    def _calculate_relevance(self, title: str, snippet: str, company_name: str) -> float:
        """Calculate relevance score for a search result"""
        score = 0.0
        
        company_words = self._clean_company_name(company_name).lower().split()
        title_lower = title.lower()
        snippet_lower = snippet.lower()
        
        # Score based on company name matches
        for word in company_words:
            if len(word) > 2:
                if word in title_lower:
                    score += 0.3
                if word in snippet_lower:
                    score += 0.2
        
        # Bonus for official indicators
        official_indicators = ['официальный', 'official', 'компания', 'company', 'сайт', 'website']
        for indicator in official_indicators:
            if indicator in title_lower:
                score += 0.1
            if indicator in snippet_lower:
                score += 0.05
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _extract_contacts_from_text(self, text: str) -> Optional[str]:
        """Extract phone numbers and emails from text"""
        contacts = []
        
        # Phone number patterns (Kazakhstan formats)
        phone_patterns = [
            r'\+7\s*\(?[0-9]{3}\)?\s*[0-9]{3}[\-\s]*[0-9]{2}[\-\s]*[0-9]{2}',
            r'8\s*\(?[0-9]{3}\)?\s*[0-9]{3}[\-\s]*[0-9]{2}[\-\s]*[0-9]{2}',
            r'\(?[0-9]{3}\)?\s*[0-9]{3}[\-\s]*[0-9]{2}[\-\s]*[0-9]{2}'
        ]
        
        for pattern in phone_patterns:
            phones = re.findall(pattern, text)
            for phone in phones:
                clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
                if len(clean_phone) >= 10:
                    contacts.append(f"тел: {phone.strip()}")
        
        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        for email in emails:
            contacts.append(f"email: {email}")
        
        return ", ".join(contacts) if contacts else None


# Singleton instance
google_search_service = GoogleSearchService() 