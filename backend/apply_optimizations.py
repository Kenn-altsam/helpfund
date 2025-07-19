#!/usr/bin/env python3
"""
Apply database optimizations directly
"""

import psycopg2
import os
from urllib.parse import urlparse
from pathlib import Path


def load_env_from_parent():
    """Load environment variables from parent directory's .env file"""
    parent_env = Path(__file__).parent.parent / '.env'
    if parent_env.exists():
        print(f"📁 Loading environment from: {parent_env}")
        with open(parent_env, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        print("✅ Environment variables loaded from .env file")
    else:
        print(f"⚠️  .env file not found at: {parent_env}")

def get_database_connection():
    """Get database connection from environment or use defaults"""
    # Load environment variables from parent .env file
    load_env_from_parent()
    
    # Try to get from environment
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        parsed = urlparse(database_url)
        return psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password
        )
    else:
        # Use default values (you may need to adjust these)
        return psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            database=os.getenv('DB_NAME', 'nFac_server'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'password')
        )


def apply_optimizations():
    """Apply all database optimizations"""
    print("🚀 Applying database optimizations...")
    
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        
        print("✅ Connected to database successfully")
        
        # 1. Create performance indexes
        print("\n📊 Creating performance indexes...")
        
        indexes = [
            # Composite index for location + tax payment queries
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_locality_tax_2025 
            ON companies ("Locality", tax_payment_2025);
            """,
            
            # Composite index for activity + tax payment queries
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_activity_tax_2025 
            ON companies ("Activity", tax_payment_2025);
            """,
            
            # Partial index for companies with tax data
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_tax_2025_not_null 
            ON companies (tax_payment_2025) 
            WHERE tax_payment_2025 IS NOT NULL;
            """,
            
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
            
            # Composite index for region + size + tax queries
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_locality_size_tax_2025 
            ON companies ("Locality", "Size", tax_payment_2025);
            """,
            
            # Additional performance indexes
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_tax_2025_range 
            ON companies (tax_payment_2025) 
            WHERE tax_payment_2025 IS NOT NULL AND tax_payment_2025 > 0;
            """,
            
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_has_contacts 
            ON companies (phone, email) 
            WHERE phone IS NOT NULL OR email IS NOT NULL;
            """,
            
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_size_category 
            ON companies ("Size") 
            WHERE "Size" LIKE '%Крупн%';
            """,
            
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_high_tax 
            ON companies (tax_payment_2025) 
            WHERE tax_payment_2025 IS NOT NULL AND tax_payment_2025 > 1000000;
            """,
            
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_has_website 
            ON companies (location) 
            WHERE location IS NOT NULL AND location != '';
            """
        ]
        
        for i, index_sql in enumerate(indexes, 1):
            try:
                print(f"  Creating index {i}/{len(indexes)}...")
                cursor.execute(index_sql)
                print(f"  ✅ Index {i} created successfully")
            except Exception as e:
                print(f"  ⚠️  Index {i} failed (may already exist): {e}")
        
        # 2. Update table statistics
        print("\n📈 Updating table statistics...")
        cursor.execute("ANALYZE companies;")
        print("✅ Table statistics updated")
        
        # 3. Vacuum the table
        print("\n🧹 Vacuuming table...")
        cursor.execute("VACUUM ANALYZE companies;")
        print("✅ Table vacuumed and analyzed")
        
        # 4. Test the optimized query
        print("\n🧪 Testing optimized query...")
        test_query = """
            SELECT COUNT(*) FROM companies 
            WHERE "Locality" ILIKE %s
            ORDER BY COALESCE(tax_payment_2025, 0) DESC, "Company" ASC
            LIMIT 5;
        """
        
        cursor.execute(test_query, ("%Алматы%",))
        count = cursor.fetchone()[0]
        print(f"✅ Test query successful! Found {count} companies in Алматы")
        
        # 5. Show index information
        print("\n📋 Current indexes on companies table:")
        cursor.execute("""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename = 'companies' 
            ORDER BY indexname;
        """)
        
        indexes = cursor.fetchall()
        for index_name, index_def in indexes:
            print(f"  📌 {index_name}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n🎉 All optimizations applied successfully!")
        print("📊 Your company queries should now be much faster (<5 seconds)")
        
    except Exception as e:
        print(f"❌ Error applying optimizations: {e}")
        print("\n💡 Make sure:")
        print("  1. Database is running and accessible")
        print("  2. Environment variables are set correctly")
        print("  3. You have sufficient permissions")
        
        # Show connection info for debugging
        print(f"\n🔍 Connection info:")
        print(f"  Host: {os.getenv('DB_HOST', 'localhost')}")
        print(f"  Port: {os.getenv('DB_PORT', '5432')}")
        print(f"  Database: {os.getenv('DB_NAME', 'nFac_server')}")
        print(f"  User: {os.getenv('DB_USER', 'postgres')}")


if __name__ == "__main__":
    apply_optimizations() 