#!/usr/bin/env python3
"""
Simple performance test for API endpoints
"""

import time
import requests
import json

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
TEST_ENDPOINTS = [
    "/companies/search?limit=50",
    "/companies/search?location=Алматы&limit=50",
    "/companies/locations/list",
    "/companies/translations/supported-cities"
]

def test_endpoint_performance(endpoint: str, iterations: int = 3):
    """Test endpoint performance"""
    print(f"\n🔍 Testing: {endpoint}")
    
    total_time = 0
    response_times = []
    
    for i in range(iterations):
        start_time = time.time()
        
        try:
            response = requests.get(f"{BASE_URL}{endpoint}")
            end_time = time.time()
            
            response_time = end_time - start_time
            response_times.append(response_time)
            total_time += response_time
            
            print(f"  Iteration {i+1}: {response_time:.3f}s (Status: {response.status_code})")
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and isinstance(data['data'], list):
                    print(f"    Data count: {len(data['data'])} items")
            
        except Exception as e:
            print(f"  Iteration {i+1}: ERROR - {e}")
    
    avg_time = total_time / iterations
    min_time = min(response_times)
    max_time = max(response_times)
    
    print(f"  📊 Results:")
    print(f"    Average: {avg_time:.3f}s")
    print(f"    Min: {min_time:.3f}s")
    print(f"    Max: {max_time:.3f}s")
    
    return avg_time

def main():
    print("🚀 API Performance Test")
    print("=" * 50)
    
    results = {}
    
    for endpoint in TEST_ENDPOINTS:
        avg_time = test_endpoint_performance(endpoint)
        results[endpoint] = avg_time
    
    print("\n" + "=" * 50)
    print("📈 SUMMARY")
    print("=" * 50)
    
    for endpoint, avg_time in results.items():
        print(f"{endpoint}: {avg_time:.3f}s")
    
    print(f"\n✅ Performance test completed!")

if __name__ == "__main__":
    main() 