"""
Database configuration and optimization settings

Optimized PostgreSQL configuration for company queries performance.
"""

import os
from typing import Dict, Any
from sqlalchemy import text


def get_database_config() -> Dict[str, Any]:
    """
    Get optimized database configuration for performance
    
    Returns:
        Dictionary with database configuration settings
    """
    return {
        # Connection settings
        "pool_size": 20,
        "max_overflow": 30,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        
        # Performance settings
        "connect_args": {
            "options": "-c timezone=utc -c statement_timeout=10000 -c lock_timeout=5000"
        }
    }


# Removed old optimization functions - now integrated into optimize_database_connection()


def optimize_database_connection(engine) -> None:
    """
    Apply comprehensive database optimizations to the engine
    
    Args:
        engine: SQLAlchemy engine instance
    """
    try:
        from sqlalchemy import text
        
        # Use SQLAlchemy connection for safe operations
        with engine.connect() as conn:
            print("🔍 Checking table schema...")
            # Check actual table schema first
            result = conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'companies' 
                ORDER BY ordinal_position;
            """))
            columns = result.fetchall()
            
            # Check for tax_data columns (actual database schema)
            tax_columns = [col[0] for col in columns if col[0] in ['tax_data_2023', 'tax_data_2024', 'tax_data_2025']]
            if tax_columns:
                print(f"📊 Found tax data columns: {tax_columns}")
                # Use the most recent tax data column (2025 if available, otherwise 2024, then 2023)
                if 'tax_data_2025' in tax_columns:
                    tax_column = 'tax_data_2025'
                elif 'tax_data_2024' in tax_columns:
                    tax_column = 'tax_data_2024'
                else:
                    tax_column = 'tax_data_2023'
                print(f"🎯 Using tax data column: {tax_column}")
            else:
                print("❌ No tax_data columns found. Skipping tax-based indexes.")
                tax_column = None
            
            # Check existing indexes to avoid recreation
            print("📋 Checking existing indexes...")
            result = conn.execute(text("""
                SELECT indexname FROM pg_indexes 
                WHERE tablename = 'companies' 
                ORDER BY indexname;
            """))
            existing_indexes = [row[0] for row in result.fetchall()]
            print(f"📊 Found {len(existing_indexes)} existing indexes")
            
            # Test the query performance
            print("🧪 Testing query performance...")
            if tax_column:
                test_query = f"""
                    SELECT COUNT(*) FROM companies 
                    WHERE "Locality" ILIKE :location;
                """
            else:
                test_query = """
                    SELECT COUNT(*) FROM companies 
                    WHERE "Locality" ILIKE :location;
                """
            
            result = conn.execute(text(test_query), {"location": "%Алматы%"})
            count = result.fetchone()[0]
            print(f"✅ Test query successful! Found {count} companies in Алматы")
            
            # Show current index status
            print("📋 Current indexes on companies table:")
            for index_name in existing_indexes:
                print(f"  📌 {index_name}")
                    
        print("✅ Database optimization check completed")
        print("💡 Note: Index creation requires manual execution outside of application context")
        print("   Run 'python -c \"from src.core.database import engine; from src.core.database_config import create_indexes; create_indexes(engine)\"' to create indexes")
        
    except Exception as e:
        print(f"⚠️  Database optimization check failed (non-critical): {e}")
        print("Database will still work, but may not be fully optimized")


def create_indexes(engine) -> None:
    """
    Create database indexes manually (run this outside of application context)
    
    Args:
        engine: SQLAlchemy engine instance
    """
    try:
        import psycopg2
        
        # Get the raw psycopg2 connection to avoid transaction issues
        raw_conn = engine.raw_connection()
        raw_conn.autocommit = True
        cursor = raw_conn.cursor()
        
        print("🔍 Checking table schema...")
        # Check actual table schema first
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'companies' 
            ORDER BY ordinal_position;
        """)
        columns = cursor.fetchall()
        
        # Check for tax_data columns (actual database schema)
        tax_columns = [col[0] for col in columns if col[0] in ['tax_data_2023', 'tax_data_2024', 'tax_data_2025']]
        if tax_columns:
            print(f"📊 Found tax data columns: {tax_columns}")
            # Use the most recent tax data column (2025 if available, otherwise 2024, then 2023)
            if 'tax_data_2025' in tax_columns:
                tax_column = 'tax_data_2025'
            elif 'tax_data_2024' in tax_columns:
                tax_column = 'tax_data_2024'
            else:
                tax_column = 'tax_data_2023'
            print(f"🎯 Using tax data column: {tax_column}")
        else:
            print("❌ No tax_data columns found. Skipping tax-based indexes.")
            tax_column = None
        
        # Create comprehensive performance indexes
        print("📊 Creating performance indexes...")
        
        indexes = []
        
        # Only add tax-related indexes if tax column exists
        if tax_column:
            indexes.extend([
                # Composite index for location + tax payment queries
                f"""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_locality_tax_2025 
                ON companies ("Locality", {tax_column});
                """,
                
                # Composite index for activity + tax payment queries
                f"""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_activity_tax_2025 
                ON companies ("Activity", {tax_column});
                """,
                
                # Partial index for companies with tax data
                f"""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_tax_2025_not_null 
                ON companies ({tax_column}) 
                WHERE {tax_column} IS NOT NULL;
                """,
                
                # Composite index for region + size + tax queries
                f"""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_locality_size_tax_2025 
                ON companies ("Locality", "Size", {tax_column});
                """,
                
                # Index for companies with non-empty tax data
                f"""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_tax_2025_not_empty 
                ON companies ({tax_column}) 
                WHERE {tax_column} IS NOT NULL AND {tax_column} != '';
                """
            ])
        
        # Add non-tax indexes
        non_tax_indexes = [
            # Full-text search index for company names
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_name_gin 
            ON companies USING gin(to_tsvector('russian', "Company"));
            """,
            
            # Full-text search index for activities
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_activity_gin 
            ON companies USING gin(to_tsvector('russian', "Activity"));
            """,
            
            # Index for company size filtering
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_size 
            ON companies ("Size");
            """,
            
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_size_category 
            ON companies ("Size") 
            WHERE "Size" LIKE '%Крупн%';
            """
        ]
        
        # Note: phone and email columns don't exist in actual database schema
        # Skipping contact-related indexes
        
        indexes.extend(non_tax_indexes)
        
        for i, index_sql in enumerate(indexes, 1):
            try:
                print(f"  Creating index {i}/{len(indexes)}...")
                cursor.execute(index_sql)
                print(f"  ✅ Index {i} created successfully")
            except Exception as e:
                print(f"  ⚠️  Index {i} failed (may already exist): {e}")
        
        # Update table statistics
        print("📈 Updating table statistics...")
        cursor.execute("ANALYZE companies;")
        print("✅ Table statistics updated")
        
        # Vacuum the table
        print("🧹 Vacuuming table...")
        cursor.execute("VACUUM ANALYZE companies;")
        print("✅ Table vacuumed and analyzed")
        
        cursor.close()
        raw_conn.close()
                    
        print("✅ Database indexes created successfully")
        
    except Exception as e:
        print(f"❌ Database index creation failed: {e}")
        print("Please run this function outside of the application context")


def get_query_performance_monitoring_sql() -> str:
    """
    Get SQL for monitoring query performance
    
    Returns:
        SQL commands for performance monitoring
    """
    return """
    -- Monitor slow queries
    SELECT 
        query,
        calls,
        total_time,
        mean_time,
        rows
    FROM pg_stat_statements 
    WHERE mean_time > 1000  -- Queries taking more than 1 second
    ORDER BY mean_time DESC 
    LIMIT 10;
    
    -- Monitor index usage
    SELECT 
        schemaname,
        tablename,
        indexname,
        idx_scan,
        idx_tup_read,
        idx_tup_fetch
    FROM pg_stat_user_indexes 
    WHERE schemaname = 'public' 
    ORDER BY idx_scan DESC;
    
    -- Monitor table statistics
    SELECT 
        schemaname,
        tablename,
        n_tup_ins,
        n_tup_upd,
        n_tup_del,
        n_live_tup,
        n_dead_tup
    FROM pg_stat_user_tables 
    WHERE schemaname = 'public';
    """ 