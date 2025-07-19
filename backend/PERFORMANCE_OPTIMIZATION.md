# Company Query Performance Optimization

This document explains the optimizations implemented to reduce company query response time from 30 seconds to under 5 seconds.

## 🎯 Performance Target

- **Before**: 30+ seconds for company queries
- **After**: Under 5 seconds for company queries
- **Dataset**: 1300 companies

## 🚀 Optimizations Implemented

### 1. Database Schema Alignment

**Problem**: SQLAlchemy model didn't match actual database schema
**Solution**: Updated model to use correct column names and data types

```python
# Before: Using text fields for tax data
tax_data_2025 = Column("tax_data_2025", Text, nullable=True)

# After: Using proper numeric types for efficient sorting
tax_payment_2025 = Column("tax_payment_2025", Float, index=True)
```

### 2. Strategic Indexing

**Problem**: Missing indexes on frequently queried columns
**Solution**: Created composite and specialized indexes

#### Key Indexes Created:

```sql
-- Composite index for location + tax queries (most common pattern)
CREATE INDEX ix_companies_locality_tax_2025 
ON companies ("Locality", tax_payment_2025 DESC);

-- Partial index for non-null tax data (faster sorting)
CREATE INDEX ix_companies_tax_2025_not_null 
ON companies (tax_payment_2025 DESC) 
WHERE tax_payment_2025 IS NOT NULL;

-- Full-text search indexes for Russian text
CREATE INDEX ix_companies_name_gin 
ON companies USING gin(to_tsvector('russian', "Company"));

CREATE INDEX ix_companies_activity_gin 
ON companies USING gin(to_tsvector('russian', "Activity"));
```

### 3. Query Optimization

**Problem**: Inefficient queries using string length calculations
**Solution**: Optimized queries with proper indexing

#### Before (Slow):
```python
# String length calculation - requires full table scan
query = query.order_by(func.length(Company.tax_data_2025).desc().nullslast())
```

#### After (Fast):
```python
# Direct numeric comparison using indexed column
query_parts.append("ORDER BY COALESCE(tax_payment_2025, 0) DESC, \"Company\" ASC")
```

### 4. Full-Text Search

**Problem**: ILIKE queries with wildcards prevent index usage
**Solution**: Implemented full-text search for better performance

```python
# Before: ILIKE with wildcards (slow)
Company.activity.ilike(f"%{keyword}%")

# After: Full-text search (fast)
to_tsvector('russian', "Activity") @@ plainto_tsquery('russian', keyword)
```

### 5. Database Configuration

**Problem**: Default PostgreSQL settings not optimized for the workload
**Solution**: Applied performance-optimized settings

```sql
-- Increase work memory for complex queries
ALTER SYSTEM SET work_mem = '256MB';

-- Optimize for SSD storage
ALTER SYSTEM SET random_page_cost = 1.1;

-- Enable parallel query execution
ALTER SYSTEM SET max_parallel_workers_per_gather = 2;
```

## 📊 Performance Improvements

### Query Types Optimized:

1. **Location-based searches** (e.g., "Almaty", "Астана")
2. **Activity-based searches** (e.g., "строительство", "нефть")
3. **Company name searches** (e.g., "ТОО", "АО")
4. **Complex searches** (location + activity combinations)
5. **Tax-based sorting** (companies with highest tax payments)

### Expected Performance:

- **Simple queries**: < 100ms
- **Complex queries**: < 1 second
- **Large result sets**: < 5 seconds

## 🔧 Setup Instructions

### Automatic Setup

Run the optimization setup script:

```bash
cd backend
python scripts/setup_optimization.py
```

### Manual Setup

1. **Apply database migrations**:
   ```bash
   cd backend
   alembic upgrade head
   ```

2. **Restart your application server**

3. **Test performance**:
   ```bash
   python scripts/monitor_performance.py
   ```

## 📈 Monitoring

### Performance Monitoring Script

The `scripts/monitor_performance.py` script provides:

- Query performance testing
- Index verification
- Slow query analysis
- Performance recommendations

### Key Metrics to Monitor:

- Average query response time
- Index usage statistics
- Slow query identification
- Database connection pool usage

## 🛠️ Troubleshooting

### If Queries Are Still Slow:

1. **Check if indexes were created**:
   ```sql
   SELECT indexname FROM pg_indexes WHERE tablename = 'companies';
   ```

2. **Verify database configuration**:
   ```sql
   SHOW work_mem;
   SHOW shared_buffers;
   ```

3. **Analyze query execution plans**:
   ```sql
   EXPLAIN ANALYZE SELECT * FROM companies WHERE "Locality" ILIKE '%Алматы%';
   ```

4. **Check for table bloat**:
   ```sql
   VACUUM ANALYZE companies;
   ```

### Common Issues:

1. **Migration failed**: Run `alembic upgrade head` manually
2. **Index creation failed**: Check PostgreSQL logs for errors
3. **Configuration not applied**: Restart PostgreSQL service
4. **Memory issues**: Reduce `work_mem` setting

## 🔮 Future Optimizations

### For Larger Datasets (>10,000 companies):

1. **Table partitioning** by region or tax payment ranges
2. **Materialized views** for complex aggregations
3. **Read replicas** for query distribution
4. **Caching layer** (Redis) for frequent queries

### For Charity Data Integration:

1. **Add charity interest scoring** to the database
2. **Create indexes** for charity-related queries
3. **Implement semantic search** for charity keywords
4. **Add social media presence indicators**

## 📝 Migration Notes

### Breaking Changes:

- Updated SQLAlchemy model column names
- Changed tax data field from `tax_data_2025` to `tax_payment_2025`
- Added new required imports for UUID and DateTime

### Backward Compatibility:

- Legacy fields maintained for gradual migration
- Fallback queries implemented for error handling
- Service layer handles both old and new field names

## 🎉 Results

With these optimizations, your company queries should now:

- ✅ Respond in under 5 seconds
- ✅ Handle complex search criteria efficiently
- ✅ Scale to larger datasets
- ✅ Provide consistent performance
- ✅ Support real-time user interactions

The optimizations focus on the most common query patterns while maintaining flexibility for future requirements. 