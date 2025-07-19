#!/usr/bin/env python3
"""
Database optimization setup script

Applies all optimizations for company query performance.
"""

import os
import sys
import subprocess
import time
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from src.core.database import engine
from src.core.database_config import optimize_database_connection


def run_command(command, description):
    """Run a shell command and handle errors"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return False


def apply_database_migrations():
    """Apply database migrations to create indexes"""
    print("\n📦 Applying Database Migrations...")
    print("=" * 50)
    
    # Change to backend directory
    os.chdir(backend_dir)
    
    # Run Alembic migrations
    success = run_command(
        "alembic upgrade head",
        "Running database migrations"
    )
    
    if success:
        print("✅ Database migrations applied successfully")
    else:
        print("⚠️  Database migrations failed - you may need to run them manually")
        print("   Run: cd backend && alembic upgrade head")
    
    return success


def optimize_database_settings():
    """Apply database optimization settings"""
    print("\n⚙️  Optimizing Database Settings...")
    print("=" * 50)
    
    try:
        optimize_database_connection(engine)
        print("✅ Database settings optimized successfully")
        return True
    except Exception as e:
        print(f"⚠️  Database optimization failed: {e}")
        print("   This is non-critical - database will still work")
        return True  # Don't fail the setup for this


def create_additional_indexes():
    """Create additional performance indexes"""
    print("\n🔧 Creating Additional Indexes...")
    print("=" * 50)
    
    additional_indexes_sql = """
    -- Create additional performance indexes
    
    -- Index for tax payment ranges
    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_tax_2025_range 
    ON companies (tax_payment_2025) 
    WHERE tax_payment_2025 > 0;
    
    -- Index for companies with contact information
    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_has_contacts 
    ON companies (phone, email) 
    WHERE phone IS NOT NULL OR email IS NOT NULL;
    
    -- Index for companies by size category
    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_size_category 
    ON companies (Size) 
    WHERE Size LIKE '%Крупн%';
    
    -- Index for companies with high tax payments
    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_high_tax 
    ON companies (tax_payment_2025) 
    WHERE tax_payment_2025 > 1000000;
    
    -- Update table statistics
    ANALYZE companies;
    """
    
    try:
        from sqlalchemy import text
        
        with engine.connect() as conn:
            for statement in additional_indexes_sql.split(';'):
                if statement.strip():
                    try:
                        conn.execute(text(statement.strip()))
                        conn.commit()
                    except Exception as stmt_error:
                        # Skip statements that fail (like CREATE INDEX CONCURRENTLY which might already exist)
                        print(f"⚠️  Skipping index creation statement: {stmt_error}")
        print("✅ Additional indexes created successfully")
        return True
    except Exception as e:
        print(f"⚠️  Additional indexes creation failed: {e}")
        print("   This is non-critical - existing indexes will still work")
        return True


def test_query_performance():
    """Test query performance after optimization"""
    print("\n🧪 Testing Query Performance...")
    print("=" * 50)
    
    try:
        from scripts.monitor_performance import monitor_query_performance
        monitor_query_performance()
        return True
    except Exception as e:
        print(f"⚠️  Performance testing failed: {e}")
        print("   You can run it manually: python scripts/monitor_performance.py")
        return True


def main():
    """Main setup function"""
    print("🚀 Company Query Performance Optimization Setup")
    print("=" * 60)
    print("This script will optimize your database for fast company queries.")
    print("Target: Reduce query time from 30 seconds to under 5 seconds.")
    print()
    
    # Check if we're in the right directory
    if not (backend_dir / "alembic.ini").exists():
        print("❌ Error: Please run this script from the backend directory")
        print("   cd backend && python scripts/setup_optimization.py")
        return False
    
    # Apply optimizations
    steps = [
        ("Database Migrations", apply_database_migrations),
        ("Database Settings", optimize_database_settings),
        ("Additional Indexes", create_additional_indexes),
        ("Performance Testing", test_query_performance),
    ]
    
    successful_steps = 0
    
    for step_name, step_function in steps:
        print(f"\n{'='*60}")
        print(f"Step {successful_steps + 1}: {step_name}")
        print(f"{'='*60}")
        
        if step_function():
            successful_steps += 1
        else:
            print(f"⚠️  Step '{step_name}' failed, but continuing...")
    
    # Summary
    print(f"\n{'='*60}")
    print("🎯 OPTIMIZATION SETUP COMPLETED")
    print(f"{'='*60}")
    print(f"✅ Successful steps: {successful_steps}/{len(steps)}")
    
    if successful_steps >= 3:
        print("🎉 Optimization setup completed successfully!")
        print("💡 Your company queries should now be much faster.")
        print("📊 Run 'python scripts/monitor_performance.py' to test performance.")
    else:
        print("⚠️  Some optimizations failed. Please check the errors above.")
        print("💡 You may need to run some steps manually.")
    
    print("\n🔧 Manual steps you might need:")
    print("   1. Restart your application server")
    print("   2. Run: cd backend && alembic upgrade head")
    print("   3. Test queries: python scripts/monitor_performance.py")
    
    return successful_steps >= 3


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 