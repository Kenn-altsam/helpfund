#!/usr/bin/env python3
"""
Index Analysis and Performance Monitoring Script

This script helps analyze current index usage and performance to identify
which indexes are being used effectively and which ones might be causing conflicts.
"""

import psycopg2
import sys
import os
from typing import Dict, List, Any

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.core.database import get_database_url

def analyze_index_usage():
    """Analyze current index usage and performance"""
    try:
        # Get database connection
        db_url = get_database_url()
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        print("🔍 Analyzing Index Usage and Performance")
        print("=" * 50)
        
        # 1. Check current indexes
        print("\n📋 Current Indexes on companies table:")
        cursor.execute("""
            SELECT 
                indexname,
                indexdef
            FROM pg_indexes 
            WHERE tablename = 'companies' 
            ORDER BY indexname;
        """)
        
        indexes = cursor.fetchall()
        for index_name, index_def in indexes:
            print(f"  📌 {index_name}")
            print(f"     {index_def[:100]}...")
        
        # 2. Check index usage statistics
        print("\n📊 Index Usage Statistics:")
        cursor.execute("""
            SELECT 
                indexname,
                idx_scan as scans,
                idx_tup_read as tuples_read,
                idx_tup_fetch as tuples_fetched,
                CASE 
                    WHEN idx_scan > 0 THEN 
                        ROUND((idx_tup_fetch::float / idx_tup_read::float) * 100, 2)
                    ELSE 0 
                END as efficiency_percent
            FROM pg_stat_user_indexes 
            WHERE tablename = 'companies' 
            ORDER BY idx_scan DESC;
        """)
        
        usage_stats = cursor.fetchall()
        for index_name, scans, tuples_read, tuples_fetched, efficiency in usage_stats:
            print(f"  📈 {index_name}:")
            print(f"     Scans: {scans}, Tuples Read: {tuples_read}, Fetched: {tuples_fetched}")
            print(f"     Efficiency: {efficiency}%")
        
        # 3. Check for unused indexes
        print("\n🚫 Potentially Unused Indexes:")
        cursor.execute("""
            SELECT 
                indexname,
                idx_scan as scans
            FROM pg_stat_user_indexes 
            WHERE tablename = 'companies' 
                AND idx_scan = 0
            ORDER BY indexname;
        """)
        
        unused_indexes = cursor.fetchall()
        if unused_indexes:
            for index_name, scans in unused_indexes:
                print(f"  ⚠️  {index_name} (0 scans)")
        else:
            print("  ✅ All indexes have been used at least once")
        
        # 4. Check for duplicate/redundant indexes
        print("\n🔄 Checking for Potential Index Conflicts:")
        cursor.execute("""
            SELECT 
                indexname,
                indexdef
            FROM pg_indexes 
            WHERE tablename = 'companies' 
                AND indexname LIKE '%locality%'
            ORDER BY indexname;
        """)
        
        locality_indexes = cursor.fetchall()
        if len(locality_indexes) > 1:
            print("  ⚠️  Multiple locality-related indexes found (potential conflicts):")
            for index_name, index_def in locality_indexes:
                print(f"     {index_name}: {index_def[:80]}...")
        
        # 5. Check table statistics
        print("\n📈 Table Statistics:")
        cursor.execute("""
            SELECT 
                n_live_tup as live_tuples,
                n_dead_tup as dead_tuples,
                last_vacuum,
                last_autovacuum,
                last_analyze,
                last_autoanalyze
            FROM pg_stat_user_tables 
            WHERE tablename = 'companies';
        """)
        
        table_stats = cursor.fetchone()
        if table_stats:
            live_tuples, dead_tuples, last_vacuum, last_autovacuum, last_analyze, last_autoanalyze = table_stats
            print(f"  📊 Live tuples: {live_tuples:,}")
            print(f"  📊 Dead tuples: {dead_tuples:,}")
            print(f"  📊 Dead tuple ratio: {round((dead_tuples / (live_tuples + dead_tuples)) * 100, 2)}%")
            print(f"  🧹 Last vacuum: {last_vacuum}")
            print(f"  📊 Last analyze: {last_analyze}")
        
        # 6. Recommendations
        print("\n💡 Recommendations:")
        print("  1. If you see multiple locality-related indexes, consider dropping redundant ones")
        print("  2. Indexes with 0 scans might be candidates for removal")
        print("  3. High dead tuple ratio (>10%) suggests need for VACUUM")
        print("  4. Run the optimized index creation script to replace conflicting indexes")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error analyzing indexes: {e}")

def check_query_performance():
    """Check recent query performance"""
    try:
        db_url = get_database_url()
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        print("\n🔍 Recent Query Performance (if pg_stat_statements is enabled):")
        print("=" * 50)
        
        # Check if pg_stat_statements is available
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
            );
        """)
        
        if cursor.fetchone()[0]:
            cursor.execute("""
                SELECT 
                    query,
                    calls,
                    total_time,
                    mean_time,
                    rows
                FROM pg_stat_statements 
                WHERE query LIKE '%companies%'
                    AND mean_time > 100  -- Queries taking more than 100ms
                ORDER BY mean_time DESC 
                LIMIT 5;
            """)
            
            slow_queries = cursor.fetchall()
            if slow_queries:
                print("🐌 Slow queries on companies table:")
                for query, calls, total_time, mean_time, rows in slow_queries:
                    print(f"  ⏱️  {mean_time:.2f}ms avg ({calls} calls)")
                    print(f"     Rows: {rows}")
                    print(f"     Query: {query[:100]}...")
                    print()
            else:
                print("  ✅ No slow queries found")
        else:
            print("  ℹ️  pg_stat_statements extension not enabled")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking query performance: {e}")

if __name__ == "__main__":
    analyze_index_usage()
    check_query_performance() 