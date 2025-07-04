#!/usr/bin/env python3
"""
Quick Start Script for KGD Tax Parser

This script provides a simple way to get started with the KGD parser.
It will parse a few companies from your existing CSV files and save the results.

Usage:
    cd parser/
    python quick_start.py

Note: Make sure to run this script from the parser/ directory!
"""

import asyncio
import sys
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.append(str(Path(__file__).parent))

from kgd_tax_parser import KGDTaxParser, load_companies_from_csv


async def quick_start():
    """Quick start function to test the parser"""
    print("🚀 KGD Tax Parser - Quick Start")
    print("=" * 50)
    
    # Check if we're in the right directory
    current_dir = Path.cwd()
    if not (current_dir / "kgd_tax_parser.py").exists():
        print("❌ Error: This script must be run from the parser/ directory")
        print("Please run:")
        print("   cd parser/")
        print("   python quick_start.py")
        return
    
    # Check if required modules are available
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ Error: Playwright not installed")
        print("Please install dependencies:")
        print("   pip install -r ../requirements.txt")
        print("   playwright install chromium")
        return
    
    # Find existing CSV files
    regions_dir = Path("regions")
    csv_files = list(regions_dir.glob("*.csv"))
    
    if not csv_files:
        print("❌ No CSV files found in regions/")
        print("Please make sure you have company data CSV files in that directory")
        return
    
    # Use the first CSV file found
    csv_file = csv_files[0]
    print(f"📂 Using CSV file: {csv_file}")
    
    # Load companies
    companies = await load_companies_from_csv(str(csv_file))
    
    if not companies:
        print("❌ No companies found in CSV file")
        return
    
    print(f"📊 Found {len(companies)} companies")
    
    # Ask user how many companies to process
    while True:
        try:
            max_companies = int(input(f"How many companies to process? (1-{min(len(companies), 20)}): "))
            if 1 <= max_companies <= min(len(companies), 20):
                break
            else:
                print(f"Please enter a number between 1 and {min(len(companies), 20)}")
        except ValueError:
            print("Please enter a valid number")
    
    # Select companies to process
    test_companies = companies[:max_companies]
    
    print(f"\n🎯 Will process {len(test_companies)} companies:")
    for i, company in enumerate(test_companies, 1):
        print(f"  {i}. {company['name']} (BIN: {company['bin']})")
    
    # Ask for confirmation
    confirm = input(f"\nProceed with parsing? (y/N): ").strip().lower()
    if confirm != 'y':
        print("❌ Cancelled by user")
        return
    
    # Create parser with manual CAPTCHA solving (safest option)
    parser = KGDTaxParser(captcha_method="manual")
    
    print(f"\n🔧 Configuration:")
    print(f"   CAPTCHA method: Manual (you'll need to solve CAPTCHAs manually)")
    print(f"   Browser mode: Non-headless (you'll see the browser)")
    print(f"   Delay between requests: 3 seconds")
    print(f"   Total estimated time: {len(test_companies) * 3 / 60:.1f} minutes")
    
    print(f"\n⚠️  Important notes:")
    print(f"   - Keep the browser window visible")
    print(f"   - Solve CAPTCHAs when prompted")
    print(f"   - Don't close the browser manually")
    print(f"   - Results will be saved to kgd_data/")
    
    input("\nPress Enter to start parsing...")
    
    # Start parsing
    try:
        await parser.process_companies(test_companies, delay=3)
        
        # Show results
        print(f"\n🎉 Parsing completed!")
        print(f"📁 Check results in:")
        print(f"   - kgd_data/company_tax_data.csv (successful results)")
        print(f"   - kgd_data/failed_searches.csv (failed searches)")
        print(f"   - kgd_data/search_log.csv (detailed log)")
        
        # Quick stats
        data_file = Path("kgd_data/company_tax_data.csv")
        if data_file.exists():
            with open(data_file, 'r') as f:
                lines = len(f.readlines()) - 1  # Minus header
            print(f"✅ Successfully parsed: {lines} companies")
        
    except Exception as e:
        print(f"❌ Error during parsing: {e}")
        print("Check the error logs for more details")


if __name__ == "__main__":
    asyncio.run(quick_start()) 