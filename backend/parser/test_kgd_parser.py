#!/usr/bin/env python3
"""
Test script for KGD Tax Parser

This script demonstrates how to use the KGD parser with different configurations
and test scenarios.

Usage:
    python parser/test_kgd_parser.py
"""

import asyncio
import os
from pathlib import Path

from kgd_tax_parser import KGDTaxParser, load_companies_from_csv
from kgd_data_importer import KGDDataImporter


async def test_single_company():
    """Test parsing a single company (with fake BIN for demo)"""
    print("🧪 Testing single company search...")
    
    parser = KGDTaxParser(captcha_method="manual")  # Use manual CAPTCHA solving
    await parser.init_browser(headless=False)  # Show browser for debugging
    
    # Test with a real BIN number (replace with actual)
    test_bin = "123456789012"  # Replace with real BIN
    test_name = "Test Company"
    
    print(f"Searching for BIN: {test_bin}")
    result = await parser.search_company(test_bin, test_name)
    
    print(f"\nResult: {result}")
    
    await parser.close()
    
    return result["status"] == "success"


async def test_csv_loading():
    """Test loading companies from CSV"""
    print("📂 Testing CSV loading...")
    
    # Try to load from an existing CSV file
    csv_files = [
        "parser/regions/2015-kazakhstan-astana-311.csv",
        "parser/regions/2015-kazakhstan-almaty-311.csv"
    ]
    
    for csv_file in csv_files:
        if Path(csv_file).exists():
            companies = await load_companies_from_csv(csv_file)
            if companies:
                print(f"✅ Loaded {len(companies)} companies from {csv_file}")
                print(f"Sample: {companies[0]}")
                return companies[:5]  # Return first 5 for testing
            
    print("❌ No CSV files found")
    return []


async def test_batch_parsing():
    """Test parsing multiple companies"""
    print("⚡ Testing batch parsing...")
    
    # Load test companies
    companies = await test_csv_loading()
    
    if not companies:
        print("❌ No companies to test")
        return False
    
    # Limit to first 3 companies for testing
    test_companies = companies[:3]
    
    parser = KGDTaxParser(
        captcha_method="manual",  # Change to "2captcha" if you have API key
    )
    
    # Process with longer delays for testing
    await parser.process_companies(test_companies, delay=5)
    
    return True


async def test_database_connection():
    """Test database connection and import"""
    print("🗄️ Testing database connection...")
    
    importer = KGDDataImporter()
    
    try:
        await importer.connect()
        print("✅ Database connection successful")
        
        # Test adding tax columns
        await importer.ensure_tax_columns_exist()
        
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False
    finally:
        await importer.disconnect()


async def test_full_workflow():
    """Test complete workflow: parse -> save -> import"""
    print("🔄 Testing full workflow...")
    
    # Step 1: Parse a few companies
    companies = await test_csv_loading()
    if not companies:
        print("❌ No companies for full workflow test")
        return False
    
    # Use only 2 companies for full test
    test_companies = companies[:2]
    
    parser = KGDTaxParser(captcha_method="manual")
    print("Step 1: Parsing companies...")
    await parser.process_companies(test_companies, delay=3)
    
    # Step 2: Import to database
    print("Step 2: Importing to database...")
    importer = KGDDataImporter()
    await importer.import_tax_data()
    
    print("✅ Full workflow completed!")
    return True


async def interactive_test():
    """Interactive test menu"""
    while True:
        print("\n" + "="*50)
        print("🧪 KGD Parser Test Menu")
        print("="*50)
        print("1. Test single company search")
        print("2. Test CSV loading")
        print("3. Test batch parsing (3 companies)")
        print("4. Test database connection")
        print("5. Test full workflow")
        print("6. Show parser statistics")
        print("0. Exit")
        
        choice = input("\nEnter your choice (0-6): ").strip()
        
        try:
            if choice == "0":
                print("👋 Goodbye!")
                break
            elif choice == "1":
                success = await test_single_company()
                print(f"✅ Test completed successfully" if success else "❌ Test failed")
            elif choice == "2":
                companies = await test_csv_loading()
                print(f"📊 Found {len(companies)} companies" if companies else "❌ No companies found")
            elif choice == "3":
                success = await test_batch_parsing()
                print(f"✅ Batch test completed" if success else "❌ Batch test failed")
            elif choice == "4":
                success = await test_database_connection()
                print(f"✅ Database test passed" if success else "❌ Database test failed")
            elif choice == "5":
                success = await test_full_workflow()
                print(f"✅ Full workflow completed" if success else "❌ Workflow failed")
            elif choice == "6":
                await show_statistics()
            else:
                print("❌ Invalid choice")
                
        except Exception as e:
            print(f"❌ Test error: {e}")
        
        input("\nPress Enter to continue...")


async def show_statistics():
    """Show parser and database statistics"""
    print("📊 Parser Statistics")
    print("-" * 30)
    
    # Check if data files exist
    data_dir = Path("parser/kgd_data")
    
    files_info = [
        ("Tax data", data_dir / "company_tax_data.csv"),
        ("Failed searches", data_dir / "failed_searches.csv"),
        ("Search log", data_dir / "search_log.csv"),
        ("Import log", data_dir / "import_log.csv"),
        ("Import errors", data_dir / "import_errors.csv")
    ]
    
    for name, file_path in files_info:
        if file_path.exists():
            # Count lines in CSV (minus header)
            with open(file_path, 'r') as f:
                lines = len(f.readlines()) - 1
            print(f"{name}: {lines} records")
        else:
            print(f"{name}: No data")
    
    # Database statistics
    print("\n🗄️ Database Statistics")
    print("-" * 30)
    try:
        from kgd_data_importer import get_database_stats
        await get_database_stats()
    except Exception as e:
        print(f"❌ Could not get database stats: {e}")


def print_setup_instructions():
    """Print setup instructions"""
    print("🚀 KGD Parser Setup Instructions")
    print("="*50)
    print("1. Install dependencies:")
    print("   pip install -r requirements.txt")
    print("   playwright install chromium")
    print()
    print("2. Setup environment variables (optional):")
    print("   export CAPTCHA_API_KEY='your_2captcha_api_key'")
    print("   export DATABASE_URL='postgresql://user:pass@localhost:5432/Ayala_database'")
    print()
    print("3. For 2captcha setup:")
    print("   - Register at https://2captcha.com")
    print("   - Get API key from dashboard")
    print("   - Add balance to your account")
    print()
    print("4. For database setup:")
    print("   - Make sure PostgreSQL is running")
    print("   - Database 'Ayala_database' should exist")
    print("   - Companies table should exist")
    print()


async def main():
    """Main test function"""
    print_setup_instructions()
    
    print("Starting interactive test...")
    await interactive_test()


if __name__ == "__main__":
    asyncio.run(main()) 