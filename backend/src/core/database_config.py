"""
Database configuration and optimization settings

Optimized PostgreSQL configuration for company queries performance.
"""

import os
from typing import Dict, Any


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


def get_postgresql_optimization_sql() -> str:
    """
    Get SQL commands to optimize PostgreSQL for company queries
    
    Returns:
        SQL commands for database optimization
    """
    return """
    -- Optimize PostgreSQL settings for company queries
    
    -- Increase work memory for complex queries
    ALTER SYSTEM SET work_mem = '256MB';
    
    -- Increase shared buffers for better caching
    ALTER SYSTEM SET shared_buffers = '256MB';
    
    -- Optimize effective cache size
    ALTER SYSTEM SET effective_cache_size = '1GB';
    
    -- Enable parallel query execution
    ALTER SYSTEM SET max_parallel_workers_per_gather = 2;
    ALTER SYSTEM SET max_parallel_workers = 4;
    
    -- Optimize random page cost for SSD
    ALTER SYSTEM SET random_page_cost = 1.1;
    
    -- Enable query plan caching
    ALTER SYSTEM SET plan_cache_mode = 'auto';
    
    -- Optimize checkpoint settings
    ALTER SYSTEM SET checkpoint_completion_target = 0.9;
    ALTER SYSTEM SET wal_buffers = '16MB';
    
    -- Enable statistics collection
    ALTER SYSTEM SET track_activities = on;
    ALTER SYSTEM SET track_counts = on;
    ALTER SYSTEM SET track_io_timing = on;
    
    -- Reload configuration
    SELECT pg_reload_conf();
    """


def get_company_table_optimization_sql() -> str:
    """
    Get SQL commands to optimize the companies table specifically
    
    Returns:
        SQL commands for table optimization
    """
    return """
    -- Optimize companies table for better query performance
    
    -- Update table statistics
    ANALYZE companies;
    
    -- Vacuum the table to reclaim space and update statistics
    VACUUM ANALYZE companies;
    
    -- Create additional performance indexes if needed
    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_tax_2025_range 
    ON companies (tax_payment_2025) 
    WHERE tax_payment_2025 > 0;
    
    -- Create index for charity-related queries (if you add charity fields later)
    -- CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_charity_interest 
    -- ON companies (charity_interest_score) 
    -- WHERE charity_interest_score > 0;
    
    -- Create index for website/social media presence
    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_companies_has_website 
    ON companies (location) 
    WHERE location IS NOT NULL AND location != '';
    """


def optimize_database_connection(engine) -> None:
    """
    Apply database optimizations to the engine
    
    Args:
        engine: SQLAlchemy engine instance
    """
    try:
        with engine.connect() as conn:
            # Apply PostgreSQL optimizations
            optimization_sql = get_postgresql_optimization_sql()
            for statement in optimization_sql.split(';'):
                if statement.strip():
                    conn.execute(statement)
            
            # Apply table-specific optimizations
            table_optimization_sql = get_company_table_optimization_sql()
            for statement in table_optimization_sql.split(';'):
                if statement.strip():
                    conn.execute(statement)
                    
        print("✅ Database optimizations applied successfully")
        
    except Exception as e:
        print(f"⚠️  Database optimization failed (non-critical): {e}")
        print("Database will still work, but may not be fully optimized")


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