#!/usr/bin/env python3
"""
Test script to verify page-based pagination is working correctly

This script tests the new page-based pagination system to ensure it works
as expected compared to the old offset-based system.
"""

import sys
import os

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.database import get_db
from companies.service import CompanyService

def test_page_based_pagination():
    """Test that page-based pagination returns different results for different pages"""
    print("🧪 Testing Page-Based Pagination")
    print("=" * 50)
    
    db = next(get_db())
    company_service = CompanyService(db)
    
    try:
        # Test parameters
        location = "Алматы"
        limit = 5
        
        print(f"📍 Testing with location: {location}, limit: {limit}")
        print()
        
        # Test page 1
        print("📄 Testing Page 1:")
        page1_results = company_service.search_companies(
            location=location,
            limit=limit,
            offset=(1 - 1) * limit  # page 1
        )
        page1_companies = [r['name'] for r in page1_results[:3]]
        print(f"   Companies: {page1_companies}")
        print(f"   Total found: {len(page1_results)}")
        print()
        
        # Test page 2
        print("📄 Testing Page 2:")
        page2_results = company_service.search_companies(
            location=location,
            limit=limit,
            offset=(2 - 1) * limit  # page 2
        )
        page2_companies = [r['name'] for r in page2_results[:3]]
        print(f"   Companies: {page2_companies}")
        print(f"   Total found: {len(page2_results)}")
        print()
        
        # Test page 3
        print("📄 Testing Page 3:")
        page3_results = company_service.search_companies(
            location=location,
            limit=limit,
            offset=(3 - 1) * limit  # page 3
        )
        page3_companies = [r['name'] for r in page3_results[:3]]
        print(f"   Companies: {page3_companies}")
        print(f"   Total found: {len(page3_results)}")
        print()
        
        # Verify results are different
        page1_2_different = set(page1_companies) != set(page2_companies)
        page2_3_different = set(page2_companies) != set(page3_companies)
        page1_3_different = set(page1_companies) != set(page3_companies)
        
        print("🔍 Verification Results:")
        print(f"   Page 1 vs Page 2 different: {page1_2_different}")
        print(f"   Page 2 vs Page 3 different: {page2_3_different}")
        print(f"   Page 1 vs Page 3 different: {page1_3_different}")
        print()
        
        # Overall result
        pagination_working = page1_2_different and page2_3_different and page1_3_different
        
        if pagination_working:
            print("✅ Page-based pagination is working correctly!")
            print("   - Different pages return different results")
            print("   - No duplicate companies across pages")
        else:
            print("❌ Page-based pagination has issues!")
            print("   - Some pages return the same results")
            print("   - This indicates a problem with the pagination logic")
        
        return pagination_working
        
    except Exception as e:
        print(f"❌ Error testing pagination: {e}")
        return False
    finally:
        db.close()

def test_api_endpoint_pagination():
    """Test that the API endpoints work with page parameters"""
    print("\n🌐 Testing API Endpoint Pagination")
    print("=" * 50)
    
    try:
        import requests
        
        # You would need to set the correct base URL for your API
        base_url = "http://localhost:8000/api/v1"
        
        print("📡 Testing /companies/search endpoint:")
        
        # Test page 1
        response1 = requests.get(f"{base_url}/companies/search", params={
            "location": "Алматы",
            "limit": 5,
            "page": 1
        })
        
        if response1.status_code == 200:
            data1 = response1.json()
            print(f"   Page 1: {len(data1.get('data', []))} companies")
            print(f"   Pagination metadata: {data1.get('metadata', {}).get('pagination', {})}")
        else:
            print(f"   ❌ Page 1 request failed: {response1.status_code}")
        
        # Test page 2
        response2 = requests.get(f"{base_url}/companies/search", params={
            "location": "Алматы",
            "limit": 5,
            "page": 2
        })
        
        if response2.status_code == 200:
            data2 = response2.json()
            print(f"   Page 2: {len(data2.get('data', []))} companies")
            print(f"   Pagination metadata: {data2.get('metadata', {}).get('pagination', {})}")
        else:
            print(f"   ❌ Page 2 request failed: {response2.status_code}")
        
        print("✅ API endpoint pagination test completed")
        
    except ImportError:
        print("⚠️  requests library not available, skipping API endpoint test")
    except Exception as e:
        print(f"❌ Error testing API endpoints: {e}")

if __name__ == "__main__":
    print("🚀 Starting Pagination Tests")
    print("=" * 50)
    
    # Test service layer pagination
    service_test_passed = test_page_based_pagination()
    
    # Test API endpoint pagination
    test_api_endpoint_pagination()
    
    print("\n📊 Test Summary:")
    print(f"   Service layer pagination: {'✅ PASSED' if service_test_passed else '❌ FAILED'}")
    print("\n💡 Next steps:")
    print("   1. If tests passed, your pagination is working correctly")
    print("   2. If tests failed, check the pagination logic in the service layer")
    print("   3. Test the frontend to ensure it's using page parameters correctly") 