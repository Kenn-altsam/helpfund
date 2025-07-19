#!/usr/bin/env python3
"""
Test script to verify offset functionality in company search.
"""

import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from src.core.database import get_db
from src.companies.service import CompanyService

def test_offset_functionality():
    """Test that offset is working correctly in company search."""
    print("🧪 Testing offset functionality...")
    
    # Get database session
    db = next(get_db())
    
    try:
        company_service = CompanyService(db)
        
        # Test the offset functionality
        test_results = company_service.test_offset_functionality("Алматы")
        
        print(f"\n📊 Test Results:")
        print(f"Offset 0 results: {test_results['offset_0_results']}")
        print(f"Offset 5 results: {test_results['offset_5_results']}")
        print(f"Offset 10 results: {test_results['offset_10_results']}")
        print(f"Offset 0 vs 5 different: {test_results['offset_0_5_different']}")
        print(f"Offset 5 vs 10 different: {test_results['offset_5_10_different']}")
        print(f"Offset working correctly: {test_results['offset_working']}")
        
        if test_results['offset_working']:
            print("✅ Offset functionality is working correctly!")
        else:
            print("❌ Offset functionality is NOT working correctly!")
            
        # Also test a simple search with different offsets
        print(f"\n🔍 Testing simple search with different offsets:")
        
        # Search with offset 0
        results_0 = company_service.search_companies(location="Алматы", limit=3, offset=0)
        print(f"Offset 0 (first 3): {[r['name'] for r in results_0]}")
        
        # Search with offset 3
        results_3 = company_service.search_companies(location="Алматы", limit=3, offset=3)
        print(f"Offset 3 (next 3): {[r['name'] for r in results_3]}")
        
        # Check if results are different
        names_0 = set(r['name'] for r in results_0)
        names_3 = set(r['name'] for r in results_3)
        
        if names_0 != names_3:
            print("✅ Different results with different offsets - offset is working!")
        else:
            print("❌ Same results with different offsets - offset is NOT working!")
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_offset_functionality() 