# TimescaleDB Performance Monitoring Queries for `raw_events`

This document contains SQL queries for monitoring and analyzing the performance of the `raw_events` hypertable in TimescaleDB.

## Table Schema Overview

- **Table Name**: `raw_events`
- **Partitioning**: TimescaleDB hypertable partitioned by `occurred_at`
- **Primary Key**: Composite (`id`, `occurred_at`)
- **Unique Constraint**: (`source`, `source_id`, `occurred_at`)
- **Indexes**:
  - `ix_raw_events_occurred_at` on `occurred_at`
  - `ix_raw_events_source_source_id` on (`source`, `source_id`)

## Performance Monitoring Queries

### 1. Partition Information

#### Basic Chunk Information
```sql
SELECT 
    child_schema,
    child_table,
    range_start,
    range_end,
    pg_size_pretty(pg_total_relation_size(child_schema || '.' || child_table)) as size
FROM timescaledb_information.chunks
WHERE hypertable_name = 'raw_events'
ORDER BY range_start;
```

#### Detailed Chunk Analysis
```sql
SELECT 
    c.chunk_name, 
    c.range_start, 
    c.range_end,
    c.is_compressed,
    pg_size_pretty(pg_relation_size(format('%I.%I', c.chunk_schema, c.chunk_name))) as table_size,
    pg_size_pretty(pg_indexes_size(format('%I.%I', c.chunk_schema, c.chunk_name))) as index_size,
    pg_size_pretty(pg_total_relation_size(format('%I.%I', c.chunk_schema, c.chunk_name))) as total_size,
    pg_stat_get_live_tuples(c.chunk_schema || '.' || c.chunk_name) as live_tuples,
    pg_stat_get_dead_tuples(c.chunk_schema || '.' || c.chunk_name) as dead_tuples
FROM timescaledb_information.chunks c
WHERE c.hypertable_name = 'raw_events'
ORDER BY c.range_start;
```

### 2. Data Distribution by Source

```sql
SELECT 
    source,
    COUNT(*) as event_count,
    MIN(occurred_at) as first_event,
    MAX(occurred_at) as last_event,
    COUNT(*) FILTER (WHERE processed) as processed_count,
    COUNT(*) FILTER (WHERE NOT processed) as unprocessed_count
FROM raw_events
GROUP BY source
ORDER BY event_count DESC;
```

### 3. Ingestion Lag Analysis

```sql
WITH recent_events AS (
    SELECT 
        occurred_at,
        ingested_at,
        EXTRACT(EPOCH FROM (ingested_at - occurred_at)) as lag_seconds
    FROM raw_events
    WHERE occurred_at > NOW() - INTERVAL '1 day'
)
SELECT 
    time_bucket('1 hour', occurred_at) as hour_bucket,
    COUNT(*) as event_count,
    AVG(lag_seconds) as avg_lag_seconds,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY lag_seconds) as p95_lag_seconds,
    MAX(lag_seconds) as max_lag_seconds
FROM recent_events
GROUP BY hour_bucket
ORDER BY hour_bucket DESC;
```

### 4. Payload Size Analysis

```sql
SELECT 
    time_bucket('1 day', occurred_at) as day,
    source,
    AVG(octet_length(payload::text)) as avg_payload_size_bytes,
    pg_size_pretty(SUM(octet_length(payload::text))::bigint) as total_payload_size,
    COUNT(*) as event_count
FROM raw_events
WHERE occurred_at > NOW() - INTERVAL '30 days'
GROUP BY day, source
ORDER BY day DESC, total_payload_size DESC;
```

### 5. Query Performance Analysis

```sql
SELECT 
    query,
    calls,
    total_exec_time,
    mean_exec_time,
    rows,
    100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) as cache_hit_ratio
FROM pg_stat_statements
WHERE query LIKE '%raw_events%'
ORDER BY total_exec_time DESC
LIMIT 10;
```

### 6. Index Usage Statistics

```sql
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch,
    pg_size_pretty(pg_relation_size(quote_ident(schemaname) || '.' || quote_ident(indexname))) as index_size
FROM pg_indexes
JOIN pg_stat_user_indexes USING (schemaname, tablename, indexname)
WHERE tablename = 'raw_events'
ORDER BY idx_scan DESC;
```

### 7. Time-based Data Growth

```sql
SELECT 
    time_bucket('1 day', occurred_at) as day,
    COUNT(*) as event_count,
    pg_size_pretty(SUM(pg_column_size(payload))) as payload_size
FROM raw_events
WHERE occurred_at > NOW() - INTERVAL '30 days'
GROUP BY day
ORDER BY day;
```

## Usage Notes

1. Some queries require the `pg_stat_statements` extension. Enable it with:
   ```sql
   CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
   ```

2. For production monitoring, consider:
   - Running these queries on a schedule
   - Setting up alerts for abnormal patterns
   - Adjusting time buckets based on your data volume

3. Query performance may vary based on:
   - Table size
   - System resources
   - Current database load

4. For large tables, consider adding `ANALYZE` before running these queries to ensure accurate statistics.

## License

This document is part of the Sentiment Pipeline project. Use and modification is permitted under the project's license terms.
