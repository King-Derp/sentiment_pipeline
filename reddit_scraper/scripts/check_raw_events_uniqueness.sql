-- SQL Script to Check Uniqueness of raw_events.id (Primary Key)
-- This script validates data integrity and identifies any potential duplicate issues

-- =============================================================================
-- 1. BASIC UNIQUENESS CHECK
-- =============================================================================

-- Check if there are any duplicate IDs in the raw_events table
SELECT 
    'ID Uniqueness Check' as check_type,
    COUNT(*) as total_records,
    COUNT(DISTINCT id) as unique_ids,
    COUNT(*) - COUNT(DISTINCT id) as duplicate_count,
    CASE 
        WHEN COUNT(*) = COUNT(DISTINCT id) THEN 'PASS - All IDs are unique'
        ELSE 'FAIL - Duplicate IDs found'
    END as status
FROM raw_events;

-- =============================================================================
-- 2. DETAILED DUPLICATE ANALYSIS (if any exist)
-- =============================================================================

-- Find specific duplicate IDs and their details
SELECT 
    'Duplicate ID Details' as analysis_type,
    id,
    COUNT(*) as occurrence_count,
    MIN(ingested_at) as first_ingested,
    MAX(ingested_at) as last_ingested,
    STRING_AGG(DISTINCT source, ', ') as sources
FROM raw_events 
GROUP BY id 
HAVING COUNT(*) > 1
ORDER BY COUNT(*) DESC, id;

-- =============================================================================
-- 3. SOURCE-SPECIFIC UNIQUENESS CHECK
-- =============================================================================

-- Check uniqueness within each source (reddit, etc.)
SELECT 
    'Source-Specific Uniqueness' as check_type,
    source,
    COUNT(*) as total_records,
    COUNT(DISTINCT id) as unique_ids,
    COUNT(*) - COUNT(DISTINCT id) as duplicate_count,
    ROUND(
        (COUNT(DISTINCT id)::DECIMAL / COUNT(*)) * 100, 2
    ) as uniqueness_percentage
FROM raw_events 
GROUP BY source
ORDER BY source;

-- =============================================================================
-- 4. SOURCE_ID UNIQUENESS CHECK (Reddit-specific)
-- =============================================================================

-- Check uniqueness of source_id within reddit source
-- (This should match the Reddit submission IDs)
SELECT 
    'Reddit Source ID Uniqueness' as check_type,
    COUNT(*) as total_reddit_records,
    COUNT(DISTINCT source_id) as unique_source_ids,
    COUNT(*) - COUNT(DISTINCT source_id) as duplicate_source_ids,
    CASE 
        WHEN COUNT(*) = COUNT(DISTINCT source_id) THEN 'PASS - All Reddit source_ids are unique'
        ELSE 'FAIL - Duplicate Reddit source_ids found'
    END as status
FROM raw_events 
WHERE source = 'reddit';

-- =============================================================================
-- 5. REDDIT SOURCE_ID DUPLICATE DETAILS
-- =============================================================================

-- Find duplicate Reddit source_ids (if any)
SELECT 
    'Duplicate Reddit Source IDs' as analysis_type,
    source_id,
    COUNT(*) as occurrence_count,
    MIN(ingested_at) as first_ingested,
    MAX(ingested_at) as last_ingested,
    STRING_AGG(id::text, ', ') as primary_key_ids
FROM raw_events 
WHERE source = 'reddit'
GROUP BY source_id 
HAVING COUNT(*) > 1
ORDER BY COUNT(*) DESC, source_id;

-- =============================================================================
-- 6. TEMPORAL ANALYSIS OF DUPLICATES
-- =============================================================================

-- Analyze when duplicates were created (time-based analysis)
WITH duplicate_analysis AS (
    SELECT 
        id,
        ingested_at,
        ROW_NUMBER() OVER (PARTITION BY id ORDER BY ingested_at) as occurrence_order
    FROM raw_events 
    WHERE id IN (
        SELECT id 
        FROM raw_events 
        GROUP BY id 
        HAVING COUNT(*) > 1
    )
)
SELECT 
    'Temporal Duplicate Analysis' as analysis_type,
    DATE_TRUNC('hour', ingested_at) as ingestion_hour,
    COUNT(*) as duplicate_records_created,
    COUNT(DISTINCT id) as unique_duplicate_ids
FROM duplicate_analysis 
WHERE occurrence_order > 1
GROUP BY DATE_TRUNC('hour', ingested_at)
ORDER BY ingestion_hour DESC;

-- =============================================================================
-- 7. COMPREHENSIVE SUMMARY REPORT
-- =============================================================================

-- Overall data integrity summary
WITH summary_stats AS (
    SELECT 
        COUNT(*) as total_records,
        COUNT(DISTINCT id) as unique_primary_keys,
        COUNT(DISTINCT source_id) FILTER (WHERE source = 'reddit') as unique_reddit_source_ids,
        COUNT(*) FILTER (WHERE source = 'reddit') as total_reddit_records,
        MIN(ingested_at) as earliest_record,
        MAX(ingested_at) as latest_record
    FROM raw_events
)
SELECT 
    'COMPREHENSIVE SUMMARY REPORT' as report_type,
    total_records,
    unique_primary_keys,
    total_records - unique_primary_keys as primary_key_duplicates,
    total_reddit_records,
    unique_reddit_source_ids,
    total_reddit_records - unique_reddit_source_ids as reddit_source_id_duplicates,
    ROUND(
        (unique_primary_keys::DECIMAL / total_records) * 100, 2
    ) as primary_key_uniqueness_percentage,
    ROUND(
        (unique_reddit_source_ids::DECIMAL / total_reddit_records) * 100, 2
    ) as reddit_source_id_uniqueness_percentage,
    earliest_record,
    latest_record,
    CASE 
        WHEN total_records = unique_primary_keys AND total_reddit_records = unique_reddit_source_ids 
        THEN '✅ EXCELLENT - Perfect data integrity'
        WHEN total_records = unique_primary_keys 
        THEN '⚠️ GOOD - Primary keys unique, but Reddit source_id duplicates exist'
        ELSE '❌ ISSUES - Primary key duplicates detected'
    END as overall_status
FROM summary_stats;

-- =============================================================================
-- 8. RECOMMENDED ACTIONS (if duplicates found)
-- =============================================================================

-- Generate cleanup recommendations
SELECT 
    'RECOMMENDED ACTIONS' as action_type,
    CASE 
        WHEN EXISTS (SELECT 1 FROM raw_events GROUP BY id HAVING COUNT(*) > 1)
        THEN 'PRIMARY KEY DUPLICATES DETECTED:
              1. Review duplicate records above
              2. Identify root cause (reconciliation process, data import, etc.)
              3. Consider implementing deduplication logic
              4. Review unique constraints on the table'
        WHEN EXISTS (
            SELECT 1 FROM raw_events 
            WHERE source = 'reddit' 
            GROUP BY source_id 
            HAVING COUNT(*) > 1
        )
        THEN 'REDDIT SOURCE_ID DUPLICATES DETECTED:
              1. Review Reddit source_id duplicates above
              2. Check reconciliation process for Reddit data
              3. Verify CSV data quality
              4. Consider adding unique constraint on (source, source_id)'
        ELSE 'NO DUPLICATES FOUND:
              ✅ Data integrity is excellent
              ✅ All primary keys are unique
              ✅ All Reddit source_ids are unique
              ✅ No action required'
    END as recommendations;
