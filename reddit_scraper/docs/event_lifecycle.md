# Event Lifecycle Documentation

This document describes the complete lifecycle of events from Reddit scraping through sentiment analysis processing.

## Overview

Events flow through the Sentiment Pipeline in the following stages:
1. **Collection**: Reddit scraper collects submissions
2. **Ingestion**: Events stored in `raw_events` table
3. **Claiming**: Sentiment analyzer claims unprocessed events
4. **Processing**: Sentiment analysis performed
5. **Completion**: Results stored and events marked as processed

## Event States

### Database Fields for State Management

The `raw_events` table uses the following fields to track event processing state:

```sql
-- Event processing state fields
processed BOOLEAN DEFAULT FALSE,        -- Whether event has been processed
processed_at TIMESTAMPTZ,              -- When processing completed
```

**Important**: The current implementation uses a boolean `processed` field, not a string `processing_status` field as mentioned in some older documentation.

### State Transitions

```
[Unprocessed] → [Claimed] → [Processing] → [Completed]
     ↓              ↓            ↓            ↓
processed=FALSE  processed=FALSE  processed=FALSE  processed=TRUE
processed_at=NULL processed_at=NULL processed_at=NULL processed_at=<timestamp>
```

## Event Collection (Reddit Scraper)

### 1. Data Collection
- Reddit scraper collects submissions from configured subreddits
- Creates `RawEventDTO` objects with standardized structure
- Assigns unique `event_id` (UUID) to each event

### 2. Data Storage
- Stores events in TimescaleDB `raw_events` hypertable
- Initial state: `processed = FALSE`, `processed_at = NULL`
- Uses `ON CONFLICT DO NOTHING` to prevent duplicates

### 3. Content Preparation
- `RawEventDTO.content` computed field extracts text for analysis
- Combines `payload.title` and `payload.selftext`
- Provides ready-to-analyze text for sentiment processing

## Event Processing (Sentiment Analyzer)

### 1. Event Claiming

The sentiment analyzer uses the following query pattern to claim unprocessed events:

```sql
-- Query for unprocessed events
SELECT * FROM raw_events 
WHERE processed IS FALSE 
ORDER BY occurred_at ASC 
LIMIT <batch_size>;
```

**Key Points**:
- Uses `processed.is_(False)` in SQLAlchemy (not `processed == False`)
- Handles three-state boolean logic: `True`, `False`, `NULL`
- Orders by `occurred_at` for chronological processing

### 2. Content Extraction

```python
# Sentiment analyzer accesses content via RawEventDTO
event_dto = RawEventDTO.from_orm(raw_event_orm)
text_to_analyze = event_dto.content  # Computed field
```

### 3. Sentiment Analysis
- Processes the extracted content using ML models
- Generates sentiment scores and metrics
- Stores results in `sentiment_results` table

### 4. Event Completion

```sql
-- Mark event as processed
UPDATE raw_events 
SET processed = TRUE, processed_at = NOW() 
WHERE id = <event_id>;
```

## Data Model Relationships

### Primary Keys and References

```python
# Internal vs External IDs
raw_event.id              # Internal database ID (auto-increment)
raw_event.event_id        # External UUID for RawEventDTO
raw_event.source_id       # Reddit submission ID (e.g., "abc123")

# Sentiment results reference internal ID
sentiment_result.event_id = raw_event.id  # References internal DB ID
```

**Important Distinction**:
- **Internal IDs**: Numeric auto-incrementing primary keys for database relationships
- **External IDs**: String identifiers from event sources (Reddit, etc.)
- **Event IDs**: UUIDs for DTO-level identification

### Content Field Implementation

The `RawEventDTO.content` field is a Pydantic computed field:

```python
@computed_field
@property
def content(self) -> str:
    """Extract text content for sentiment analysis."""
    if not self.payload:
        return ""
    
    title = self.payload.get('title', '')
    selftext = self.payload.get('selftext', '')
    
    # Combine title and selftext with separator
    content_parts = [part.strip() for part in [title, selftext] if part.strip()]
    return ' '.join(content_parts)
```

## Error Handling and Edge Cases

### Processing Failures

When sentiment analysis fails:
1. Event remains `processed = FALSE`
2. Error details logged to `dead_letter_events` table
3. Event can be retried in subsequent processing runs

### Duplicate Prevention

- **Database Level**: `UNIQUE` constraint on `event_id`
- **Application Level**: `ON CONFLICT DO NOTHING` in inserts
- **CSV Level**: No deduplication (raw log of processing attempts)

### State Consistency

- **Atomic Updates**: Processing state changes in single transaction
- **Rollback Handling**: Failed processing doesn't mark events as complete
- **Recovery**: Unprocessed events automatically picked up in next run

## Monitoring and Observability

### Key Metrics

```sql
-- Count of unprocessed events
SELECT COUNT(*) FROM raw_events WHERE processed IS FALSE;

-- Processing lag (oldest unprocessed event)
SELECT MIN(occurred_at) FROM raw_events WHERE processed IS FALSE;

-- Processing rate (events per hour)
SELECT COUNT(*) FROM raw_events 
WHERE processed_at > NOW() - INTERVAL '1 hour';
```

### Health Checks

- **Event Backlog**: Monitor count of unprocessed events
- **Processing Lag**: Alert if oldest unprocessed event exceeds threshold
- **Error Rate**: Monitor dead letter queue for processing failures

## Configuration

### Reddit Scraper Settings

```yaml
# Event creation settings
initial_backfill: true
maintenance_interval_sec: 61
auto_backfill_gap_threshold_sec: 600
```

### Sentiment Analyzer Settings

```python
# Event processing settings
BATCH_SIZE = 100  # Events processed per batch
PROCESSING_TIMEOUT = 300  # Seconds before timeout
```

## Troubleshooting

### Common Issues

1. **Events Not Being Processed**
   - Check sentiment analyzer service status
   - Verify database connectivity
   - Check for processing errors in logs

2. **Processing Lag**
   - Monitor event backlog size
   - Check sentiment analyzer performance
   - Consider scaling processing capacity

3. **State Inconsistencies**
   - Verify boolean field queries use `.is_(False)` not `== False`
   - Check for NULL values in processed field
   - Ensure atomic transaction handling

### Diagnostic Queries

```sql
-- Event state summary
SELECT 
    processed,
    COUNT(*) as count,
    MIN(occurred_at) as oldest,
    MAX(occurred_at) as newest
FROM raw_events 
GROUP BY processed;

-- Recent processing activity
SELECT 
    DATE_TRUNC('hour', processed_at) as hour,
    COUNT(*) as processed_count
FROM raw_events 
WHERE processed_at > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour;
```

## Best Practices

### For Developers

1. **Always use `.is_(False)` for boolean queries** in SQLAlchemy
2. **Handle NULL states** in boolean fields properly
3. **Use internal IDs** for database relationships
4. **Use external IDs** for logging and user-facing operations
5. **Ensure atomic state transitions** in processing logic

### For Operations

1. **Monitor event backlog** regularly
2. **Set up alerts** for processing lag
3. **Review dead letter queue** for systematic failures
4. **Verify data consistency** between services
5. **Plan capacity** based on event volume trends
