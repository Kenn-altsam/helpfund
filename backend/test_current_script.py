#!/usr/bin/env python3
"""
Test script to verify current optimization script state
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

def test_connection():
    """Test database connection and schema"""
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
        
        # Check schema
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'companies' 
            ORDER BY ordinal_position;
        """)
        columns = cursor.fetchall()
        
        print("📋 Available columns in companies table:")
        for col_name, col_type in columns:
            print(f"  - {col_name}: {col_type}")
        
        # Test a simple query
        cursor.execute("""
            SELECT COUNT(*) FROM companies 
            WHERE "Locality" ILIKE %s
            ORDER BY tax_data_2025 DESC NULLS LAST, "Company" ASC
            LIMIT 5;
        """, ("%Алматы%",))
        
        count = cursor.fetchone()[0]
        print(f"✅ Test query successful! Found {count} companies in Алматы")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_connection() 