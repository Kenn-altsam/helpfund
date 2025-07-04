"""KGD Tax Data Parser

This script scrapes tax information for companies from the KGD (Committee of State Revenues) website.
It handles CAPTCHA bypass and extracts tax payment data for companies.

Features:
- CAPTCHA handling using 2captcha service
- Company search by BIN (Business Identification Number)
- Tax data extraction for years 2020-2025
- CSV export for database integration

File layout created at runtime:
    parser/
        kgd_tax_parser.py
        kgd_data/
            company_tax_data.csv
            failed_searches.csv
            search_log.csv

Usage:
    pip install playwright 2captcha-python
    playwright install chromium
    export CAPTCHA_API_KEY="your_2captcha_api_key"  # Optional
    python parser/kgd_tax_parser.py
"""

import asyncio
import csv
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Import CAPTCHA solver
try:
    from kgd_captcha_solver import create_captcha_solver
    CAPTCHA_SOLVER_AVAILABLE = True
except ImportError:
    print("⚠️ CAPTCHA solver module not found. Install with: pip install 2captcha-python requests")
    CAPTCHA_SOLVER_AVAILABLE = False

# Configuration
KGD_URL = "https://kgd.gov.kz/ru/services/taxpayer_search/legal_entity"
BASE_DIR = Path(__file__).parent
KGD_DATA_DIR = BASE_DIR / "kgd_data"
KGD_DATA_DIR.mkdir(parents=True, exist_ok=True)

# CSV file paths
TAX_DATA_CSV = KGD_DATA_DIR / "company_tax_data.csv"
FAILED_SEARCHES_CSV = KGD_DATA_DIR / "failed_searches.csv"
SEARCH_LOG_CSV = KGD_DATA_DIR / "search_log.csv"

# CSV fieldnames
TAX_FIELDNAMES = [
    "bin",
    "company_name", 
    "search_date",
    "tax_2020",
    "tax_2021", 
    "tax_2022",
    "tax_2023",
    "tax_2024",
    "tax_2025",
    "vat_refund_2020",
    "vat_refund_2021",
    "vat_refund_2022",
    "vat_refund_2023",
    "vat_refund_2024",
    "vat_refund_2025",
]

FAILED_FIELDNAMES = [
    "bin",
    "company_name",
    "error_reason",
    "search_date"
]

LOG_FIELDNAMES = [
    "bin",
    "company_name", 
    "status",
    "search_date",
    "notes"
]


class KGDTaxParser:
    def __init__(self, captcha_api_key: Optional[str] = None, captcha_method: str = "auto"):
        self.captcha_api_key = captcha_api_key or os.getenv("CAPTCHA_API_KEY")
        self.captcha_method = captcha_method
        self.captcha_solver = None
        self.page = None
        self.browser = None
        
    async def init_browser(self, headless: bool = False):
        """Initialize browser and page"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=headless,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage'
            ]
        )
        context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        self.page = await context.new_page()
        
    async def solve_captcha(self) -> bool:
        """Attempt to solve CAPTCHA if present"""
        try:
            # Check if CAPTCHA is present
            captcha_element = await self.page.query_selector('img[src*="captcha"]')
            if not captcha_element:
                return True  # No CAPTCHA present
                
            print("🔍 CAPTCHA detected, attempting to solve...")
            
            # Initialize CAPTCHA solver if not done already
            if not self.captcha_solver and CAPTCHA_SOLVER_AVAILABLE:
                self.captcha_solver = create_captcha_solver(
                    api_key=self.captcha_api_key,
                    method=self.captcha_method
                )
            
            # Attempt to solve CAPTCHA
            if self.captcha_solver:
                solution = await self.captcha_solver.solve_captcha_from_page(self.page)
                
                if solution:
                    # Find CAPTCHA input field and enter solution
                    captcha_input = await self.page.query_selector('input[name*="captcha"]')
                    if not captcha_input:
                        captcha_input = await self.page.query_selector('input#captcha')
                    if not captcha_input:
                        captcha_input = await self.page.query_selector('input[placeholder*="код"]')
                    
                    if captcha_input:
                        await captcha_input.fill(solution)
                        print(f"✅ CAPTCHA solution entered: {solution}")
                        return True
                    else:
                        print("❌ CAPTCHA input field not found")
                        return False
                else:
                    print("❌ Failed to solve CAPTCHA")
                    return False
            else:
                # Fallback to manual solving
                print("⚠️  CAPTCHA detected but no solver available.")
                print("⏸️  Please solve CAPTCHA manually and press Enter to continue...")
                input()
                return True
                
        except Exception as e:
            print(f"❌ Error handling CAPTCHA: {e}")
            return False
    
    async def search_company(self, bin_number: str, company_name: str = "") -> Dict:
        """Search for a company by BIN number"""
        try:
            await self.page.goto(KGD_URL, timeout=60000)
            await self.page.wait_for_load_state('networkidle')
            
            # Fill in the BIN field
            bin_input = await self.page.query_selector('input[name="bin"]')
            if not bin_input:
                bin_input = await self.page.query_selector('#bin')
            
            if bin_input:
                await bin_input.fill(bin_number)
            else:
                raise Exception("BIN input field not found")
            
            # Handle CAPTCHA if present
            if not await self.solve_captcha():
                raise Exception("Failed to solve CAPTCHA")
            
            # Submit the form
            search_button = await self.page.query_selector('button[type="submit"]')
            if not search_button:
                search_button = await self.page.query_selector('input[type="submit"]')
                
            if search_button:
                await search_button.click()
            else:
                await self.page.keyboard.press('Enter')
            
            # Wait for results
            await self.page.wait_for_load_state('networkidle', timeout=30000)
            
            # Check if company was found
            error_element = await self.page.query_selector('.error, .alert-danger')
            if error_element:
                error_text = await error_element.inner_text()
                if "не найден" in error_text.lower() or "not found" in error_text.lower():
                    return {"status": "not_found", "error": "Company not found"}
            
            # Extract tax data
            tax_data = await self.extract_tax_data()
            
            return {
                "status": "success",
                "bin": bin_number,
                "company_name": company_name,
                "tax_data": tax_data
            }
            
        except PlaywrightTimeout:
            return {"status": "timeout", "error": "Page load timeout"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def extract_tax_data(self) -> Dict[str, str]:
        """Extract tax data from the results table"""
        tax_data = {
            "tax_2020": "",
            "tax_2021": "",
            "tax_2022": "",
            "tax_2023": "",
            "tax_2024": "",
            "tax_2025": "",
            "vat_refund_2020": "",
            "vat_refund_2021": "",
            "vat_refund_2022": "",
            "vat_refund_2023": "",
            "vat_refund_2024": "",
            "vat_refund_2025": "",
        }
        
        try:
            # Look for the tax table
            table = await self.page.query_selector('table.table-taxpayment')
            if not table:
                # Try alternative selectors
                table = await self.page.query_selector('table.table-bordered')
                
            if not table:
                print("⚠️  Tax table not found")
                return tax_data
            
            # Extract table rows
            rows = await table.query_selector_all('tbody tr')
            
            for row in rows:
                cells = await row.query_selector_all('td')
                if len(cells) >= 7:  # Should have 7 columns as per the HTML structure
                    cell_texts = []
                    for cell in cells:
                        text = await cell.inner_text()
                        cell_texts.append(text.strip())
                    first_cell = cell_texts[0].lower()
                    # First row: "Налоговые поступления"
                    if "налоговые поступления" in first_cell:
                        tax_data["tax_2020"] = self.clean_tax_amount(cell_texts[1])
                        tax_data["tax_2021"] = self.clean_tax_amount(cell_texts[2])
                        tax_data["tax_2022"] = self.clean_tax_amount(cell_texts[3])
                        tax_data["tax_2023"] = self.clean_tax_amount(cell_texts[4])
                        tax_data["tax_2024"] = self.clean_tax_amount(cell_texts[5])
                        tax_data["tax_2025"] = self.clean_tax_amount(cell_texts[6])
                    # Second row: "В т.ч. сумма возврата превышения НДС"
                    elif "сумма возврата" in first_cell or "возврата превышения ндс" in first_cell:
                        tax_data["vat_refund_2020"] = self.clean_tax_amount(cell_texts[1])
                        tax_data["vat_refund_2021"] = self.clean_tax_amount(cell_texts[2])
                        tax_data["vat_refund_2022"] = self.clean_tax_amount(cell_texts[3])
                        tax_data["vat_refund_2023"] = self.clean_tax_amount(cell_texts[4])
                        tax_data["vat_refund_2024"] = self.clean_tax_amount(cell_texts[5])
                        tax_data["vat_refund_2025"] = self.clean_tax_amount(cell_texts[6])
            
            print(f"📊 Extracted tax data: {tax_data}")
            return tax_data
            
        except Exception as e:
            print(f"❌ Error extracting tax data: {e}")
            return tax_data
    
    def clean_tax_amount(self, amount: str) -> str:
        """Clean and normalize tax amount strings"""
        if not amount:
            return "0"
        
        # Remove any non-numeric characters except digits, commas, dots, and minus
        cleaned = re.sub(r'[^\d,.\-]', '', amount.strip())
        
        # Handle empty or invalid values
        if not cleaned or cleaned in ['-', '.', ',']:
            return "0"
        
        # Convert to standard format (remove thousands separators, keep decimal point)
        # Assuming format like "1,234,567.89" or "1 234 567,89"
        if ',' in cleaned and '.' in cleaned:
            # US format: 1,234.56
            cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            # European format: 1234,56 or thousands separator: 1,234,567
            parts = cleaned.split(',')
            if len(parts) == 2 and len(parts[1]) <= 2:
                # Decimal comma: 1234,56
                cleaned = cleaned.replace(',', '.')
            else:
                # Thousands separator: 1,234,567
                cleaned = cleaned.replace(',', '')
        
        return cleaned
    
    async def save_tax_data(self, data: Dict):
        """Save tax data to CSV file"""
        file_exists = TAX_DATA_CSV.exists()
        
        with open(TAX_DATA_CSV, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=TAX_FIELDNAMES)
            
            if not file_exists:
                writer.writeheader()
            
            row_data = {
                "bin": data["bin"],
                "company_name": data["company_name"],
                "search_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                **data["tax_data"]
            }
            writer.writerow(row_data)
    
    async def save_failed_search(self, bin_number: str, company_name: str, error: str):
        """Save failed search to CSV file"""
        file_exists = FAILED_SEARCHES_CSV.exists()
        
        with open(FAILED_SEARCHES_CSV, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=FAILED_FIELDNAMES)
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerow({
                "bin": bin_number,
                "company_name": company_name,
                "error_reason": error,
                "search_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
    
    async def log_search(self, bin_number: str, company_name: str, status: str, notes: str = ""):
        """Log search attempt"""
        file_exists = SEARCH_LOG_CSV.exists()
        
        with open(SEARCH_LOG_CSV, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=LOG_FIELDNAMES)
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerow({
                "bin": bin_number,
                "company_name": company_name,
                "status": status,
                "search_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "notes": notes
            })
    
    async def process_companies(self, companies: List[Dict[str, str]], delay: int = 2):
        """Process multiple companies"""
        await self.init_browser(headless=False)  # Set to True for headless mode
        
        total = len(companies)
        successful = 0
        failed = 0
        
        print(f"🚀 Starting to process {total} companies...")
        
        for i, company in enumerate(companies, 1):
            bin_number = company.get("bin", "")
            company_name = company.get("name", "")
            
            print(f"\n[{i}/{total}] Processing BIN: {bin_number}, Name: {company_name}")
            
            result = await self.search_company(bin_number, company_name)
            
            if result["status"] == "success":
                await self.save_tax_data(result)
                await self.log_search(bin_number, company_name, "success")
                successful += 1
                print(f"✅ Successfully processed {company_name}")
            else:
                error_msg = result.get("error", "Unknown error")
                await self.save_failed_search(bin_number, company_name, error_msg)
                await self.log_search(bin_number, company_name, "failed", error_msg)
                failed += 1
                print(f"❌ Failed to process {company_name}: {error_msg}")
            
            # Add delay between requests to avoid being blocked
            if i < total:
                print(f"⏳ Waiting {delay} seconds before next request...")
                await asyncio.sleep(delay)
        
        await self.browser.close()
        
        print(f"\n🎉 Processing complete!")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"📁 Results saved to: {KGD_DATA_DIR}")
    
    async def close(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()


# Example usage and test functions
async def test_single_company():
    """Test with a single company"""
    parser = KGDTaxParser()
    
    # Test with a sample BIN (replace with actual BIN)
    test_companies = [
        {"bin": "123456789012", "name": "Test Company"}
    ]
    
    await parser.process_companies(test_companies)


async def load_companies_from_csv(csv_file: str) -> List[Dict[str, str]]:
    """Load companies from existing CSV file"""
    companies = []
    
    if not Path(csv_file).exists():
        print(f"❌ CSV file not found: {csv_file}")
        return companies
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Adjust field names based on your existing CSV structure
            bin_number = row.get('BIN', row.get('bin', ''))
            company_name = row.get('Company', row.get('name', row.get('company_name', '')))
            
            if bin_number:
                companies.append({
                    "bin": bin_number,
                    "name": company_name
                })
    
    print(f"📝 Loaded {len(companies)} companies from {csv_file}")
    return companies


if __name__ == "__main__":
    # Example: Load companies from existing CSV and process them
    
    # Option 1: Test with sample data
    # asyncio.run(test_single_company())
    
    # Option 2: Load from existing CSV files
    # You can specify the path to your existing company CSV file
    async def main():
        # Load companies from one of your existing region files
        csv_file = BASE_DIR / "regions" / "2015-kazakhstan-astana-311.csv"
        
        companies = await load_companies_from_csv(str(csv_file))
        
        if companies:
            # Limit to first 10 companies for testing
            test_companies = companies[:10]
            
            parser = KGDTaxParser()
            await parser.process_companies(test_companies, delay=3)
        else:
            print("❌ No companies loaded. Please check your CSV file.")
    
    asyncio.run(main()) 