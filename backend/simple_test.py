#!/usr/bin/env python3
"""
Simple test to check basic query functionality
"""

import os
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

def test_simple_query():
    """Test a very simple query"""
    try:
        import psycopg2
        
        # Load environment variables
        load_env_from_parent()
        
        # Connect to database
        conn = psycopg2.connect(
            host='localhost',
            port=os.getenv('DB_PORT', '5432'),
            database=os.getenv('DB_NAME', 'nFac_server'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'password')
        )
        
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("✅ Connected to database successfully")
        
        # Test 1: Simple count
        print("\n🧪 Test 1: Simple count")
        cursor.execute("SELECT COUNT(*) FROM companies;")
        total_count = cursor.fetchone()[0]
        print(f"✅ Total companies: {total_count}")
        
        # Test 2: Simple filter
        print("\n🧪 Test 2: Simple filter")
        cursor.execute("SELECT COUNT(*) FROM companies WHERE \"Locality\" ILIKE %s;", ("%Алматы%",))
        almaty_count = cursor.fetchone()[0]
        print(f"✅ Companies in Алматы: {almaty_count}")
        
        # Test 3: Simple order by
        print("\n🧪 Test 3: Simple order by")
        cursor.execute("SELECT \"Company\", \"Locality\" FROM companies ORDER BY \"Company\" ASC LIMIT 3;")
        companies = cursor.fetchall()
        for company in companies:
            print(f"  - {company[0]} ({company[1]})")
        
        # Test 4: Order by tax_data_2025
        print("\n🧪 Test 4: Order by tax_data_2025")
        cursor.execute("""
            SELECT \"Company\", \"Locality\", tax_payment_2025
FROM companies
WHERE tax_payment_2025 IS NOT NULL
ORDER BY tax_payment_2025 DESC NULLS LAST 
            LIMIT 3;
        """)
        tax_companies = cursor.fetchall()
        for company in tax_companies:
            print(f"  - {company[0]} ({company[1]}) - Tax: {company[2]}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple_query() 