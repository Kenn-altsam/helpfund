#!/usr/bin/env python3
"""
Performance monitoring script for company queries

Monitors query performance and provides insights for optimization.
"""

import time
import logging
from sqlalchemy import text
from src.core.database import SessionLocal
from src.companies.service import CompanyService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def monitor_query_performance():
    """Monitor the performance of company queries"""
    
    db = SessionLocal()
    company_service = CompanyService(db)
    
    # Test queries with different parameters
    test_cases = [
        {
            "name": "Location search (Almaty)",
            "params": {"location": "Almaty", "limit": 10}
        },
        {
            "name": "Activity search (строительство)",
            "params": {"activity_keywords": ["строительство"], "limit": 10}
        },
        {
            "name": "Company name search",
            "params": {"company_name": "ТОО", "limit": 10}
        },
        {
            "name": "Complex search (location + activity)",
            "params": {"location": "Астана", "activity_keywords": ["нефть"], "limit": 10}
        },
        {
            "name": "Large result set",
            "params": {"location": "Алматинская область", "limit": 50}
        }
    ]
    
    print("🚀 Starting Performance Monitoring...")
    print("=" * 60)
    
    total_time = 0
    successful_queries = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📊 Test {i}: {test_case['name']}")
        print("-" * 40)
        
        start_time = time.time()
        
        try:
            # Execute the query
            results = company_service.search_companies(**test_case['params'])
            
            end_time = time.time()
            query_time = (end_time - start_time) * 1000  # Convert to milliseconds
            
            total_time += query_time
            successful_queries += 1
            
            print(f"✅ Query completed in {query_time:.2f}ms")
            print(f"📈 Results returned: {len(results)}")
            
            # Performance assessment
            if query_time < 1000:
                print("🟢 EXCELLENT: Query under 1 second")
            elif query_time < 5000:
                print("🟡 GOOD: Query under 5 seconds")
            else:
                print("🔴 SLOW: Query over 5 seconds - needs optimization")
                
        except Exception as e:
            end_time = time.time()
            query_time = (end_time - start_time) * 1000
            print(f"❌ Query failed after {query_time:.2f}ms: {e}")
    
    print("\n" + "=" * 60)
    print("📊 PERFORMANCE SUMMARY")
    print("=" * 60)
    
    if successful_queries > 0:
        avg_time = total_time / successful_queries
        print(f"✅ Successful queries: {successful_queries}/{len(test_cases)}")
        print(f"⏱️  Average query time: {avg_time:.2f}ms")
        print(f"⏱️  Total time: {total_time:.2f}ms")
        
        if avg_time < 1000:
            print("🎉 EXCELLENT: All queries under 1 second average!")
        elif avg_time < 5000:
            print("👍 GOOD: Queries under 5 seconds average")
        else:
            print("⚠️  NEEDS OPTIMIZATION: Queries over 5 seconds average")
    else:
        print("❌ No successful queries to analyze")
    
    db.close()


def check_database_indexes():
    """Check if the performance indexes are properly created"""
    
    db = SessionLocal()
    
    print("\n🔍 Checking Database Indexes...")
    print("-" * 40)
    
    index_queries = [
        ("ix_companies_locality_tax_2025", "Composite index for location + tax"),
        ("ix_companies_activity_tax_2025", "Composite index for activity + tax"),
        ("ix_companies_tax_2025_not_null", "Partial index for non-null tax data"),
        ("ix_companies_name_gin", "Full-text search index for company names"),
        ("ix_companies_activity_gin", "Full-text search index for activities"),
        ("ix_companies_size", "Index for company size"),
        ("ix_companies_locality_size_tax_2025", "Composite index for location + size + tax")
    ]
    
    for index_name, description in index_queries:
        try:
            result = db.execute(text(f"""
                SELECT indexname, indexdef 
                FROM pg_indexes 
                WHERE indexname = '{index_name}' 
                AND schemaname = 'public'
            """))
            
            if result.fetchone():
                print(f"✅ {index_name}: {description}")
            else:
                print(f"❌ {index_name}: {description} - MISSING")
                
        except Exception as e:
            print(f"⚠️  {index_name}: Error checking - {e}")
    
    db.close()


def analyze_slow_queries():
    """Analyze slow queries from PostgreSQL statistics"""
    
    db = SessionLocal()
    
    print("\n🐌 Analyzing Slow Queries...")
    print("-" * 40)
    
    try:
        # Check if pg_stat_statements is available
        result = db.execute(text("""
            SELECT query, calls, total_time, mean_time, rows
            FROM pg_stat_statements 
            WHERE mean_time > 1000  -- Queries taking more than 1 second
            ORDER BY mean_time DESC 
            LIMIT 5
        """))
        
        slow_queries = result.fetchall()
        
        if slow_queries:
            print("Found slow queries:")
            for i, query in enumerate(slow_queries, 1):
                print(f"\n{i}. Mean time: {query.mean_time:.2f}ms")
                print(f"   Calls: {query.calls}")
                print(f"   Query: {query.query[:100]}...")
        else:
            print("✅ No slow queries found!")
            
    except Exception as e:
        print(f"⚠️  Could not analyze slow queries: {e}")
        print("   (pg_stat_statements extension might not be enabled)")
    
    db.close()


if __name__ == "__main__":
    print("🔧 Company Query Performance Monitor")
    print("=" * 60)
    
    # Check indexes first
    check_database_indexes()
    
    # Monitor query performance
    monitor_query_performance()
    
    # Analyze slow queries
    analyze_slow_queries()
    
    print("\n🎯 Performance monitoring completed!")
    print("💡 If queries are still slow, consider:")
    print("   - Running database migrations to create indexes")
    print("   - Checking PostgreSQL configuration")
    print("   - Analyzing query execution plans") 