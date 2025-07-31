# Reddit Scraper Architecture

This document describes the architecture and integration patterns for the Reddit Finance Scraper within the larger Sentiment Pipeline project.

## Overview

The Reddit Scraper is a component of the Sentiment Pipeline that:
1. Collects Reddit submissions from finance-related subreddits
2. Converts them to standardized `RawEventDTO` objects
3. Stores them in both TimescaleDB (primary) and CSV files (secondary)
4. Enables downstream processing by the sentiment_analyzer service

## Data Flow Architecture

```
Reddit API → Reddit Scraper → RawEventDTO → Storage Sinks → Sentiment Analyzer
                                    ↓
                            [TimescaleDB] + [CSV Files]
```

### 1. Data Collection
- **Source**: Reddit API via `asyncpraw` library
- **Target Subreddits**: Finance-focused communities (wallstreetbets, stocks, investing, etc.)
- **Collection Methods**:
  - **Latest Pass**: `subreddit.new(limit=None)` for recent submissions
  - **Historical Pass**: Time-windowed queries for backfill
  - **Maintenance Mode**: Periodic polling for new content

### 2. Data Transformation
- **Input**: Raw Reddit submission objects
- **Output**: Standardized `RawEventDTO` objects
- **Key Transformations**:
  - Reddit submission ID normalization (removes "t3_" prefix)
  - Timestamp conversion to UTC
  - Content extraction for sentiment analysis

### 3. Data Storage
- **Primary**: TimescaleDB `raw_events` hypertable
- **Secondary**: Local CSV files for backup/inspection

## Data Models

### RawEventDTO Structure

```python
class RawEventDTO:
    event_id: UUID          # Primary key, auto-generated
    event_type: str         # Always "reddit_submission"
    source: str             # Always "reddit"
    source_id: str          # Reddit submission ID (base36, no prefix)
    occurred_at: datetime   # When submission was created on Reddit
    ingested_at: datetime   # When scraper processed it
    payload: dict           # Complete Reddit submission data
    content: str            # Computed field: title + selftext for analysis
```

### Database Schema (raw_events table)

```sql
CREATE TABLE raw_events (
    id SERIAL PRIMARY KEY,                    -- Internal DB ID
    event_id UUID UNIQUE NOT NULL,           -- Matches RawEventDTO.event_id
    event_type VARCHAR(50) NOT NULL,         -- "reddit_submission"
    source VARCHAR(50) NOT NULL,             -- "reddit"
    source_id VARCHAR(255) NOT NULL,         -- Reddit submission ID
    occurred_at TIMESTAMPTZ NOT NULL,        -- Submission creation time
    ingested_at TIMESTAMPTZ DEFAULT NOW(),   -- Processing timestamp
    processed BOOLEAN DEFAULT FALSE,         -- For sentiment analyzer claiming
    processed_at TIMESTAMPTZ,               -- When sentiment analysis completed
    payload JSONB NOT NULL                   -- Complete Reddit data
);

-- TimescaleDB hypertable partitioned by occurred_at
SELECT create_hypertable('raw_events', 'occurred_at');
```

## Integration with Sentiment Analyzer

### Event Processing Lifecycle

1. **Event Creation**: Reddit scraper creates `RawEventDTO` and stores in `raw_events`
2. **Event Claiming**: Sentiment analyzer queries for unprocessed events (`processed = FALSE`)
3. **Content Extraction**: Uses `RawEventDTO.content` computed field for text analysis
4. **Result Storage**: Saves sentiment results with reference to original event
5. **Event Completion**: Marks event as `processed = TRUE` with timestamp

### Key Integration Points

- **Shared Database**: Both services use the same TimescaleDB instance
- **Event Claiming**: Uses boolean `processed` field (not string `processing_status`)
- **Content Field**: Computed field automatically extracts analyzable text
- **ID Relationships**: Sentiment results reference `raw_events.id` (internal DB ID)

## Storage Architecture

### Primary Storage: TimescaleDB

**Implementation**: `SQLAlchemyPostgresSink`
- **Connection**: SQLAlchemy with connection pooling
- **Deduplication**: `ON CONFLICT DO NOTHING` on `event_id`
- **Batch Processing**: Processes records in configurable batches
- **Error Handling**: Graceful rollback on failures

**Benefits**:
- High performance for time-series data
- ACID compliance
- Efficient querying for sentiment analyzer
- Automatic partitioning by time

### Secondary Storage: CSV Files

**Implementation**: `CsvSink`
- **Path**: Single consolidated file (`data/reddit_finance.csv`)
- **Format**: Standard CSV with JSON payload column
- **Mode**: Append-only for resilience
- **Timestamp Handling**: Preserves Unix timestamps as numeric values

**Benefits**:
- Local backup during database outages
- Quick data inspection and debugging
- Simple format for external analysis tools

### Composite Storage

**Implementation**: `CompositeSink`
- Writes to both TimescaleDB and CSV simultaneously
- Provides redundancy and resilience
- Configurable via `--sink composite` CLI option

## Error Handling and Resilience

### API Error Handling
- **Rate Limiting**: Respects Reddit API limits with exponential backoff
- **5xx Errors**: Retry with exponential backoff up to failure threshold
- **429 Errors**: Honor `Retry-After` header
- **Network Issues**: Graceful degradation with logging

### Storage Error Handling
- **Database Failures**: Fall back to CSV-only storage
- **Disk Space**: Monitor usage and alert on thresholds
- **Duplicate Handling**: Database-level deduplication prevents duplicates

### Recovery Mechanisms
- **Auto-backfill**: Detects gaps and automatically fills them
- **Maintenance Mode**: Continuous monitoring for new content
- **Graceful Shutdown**: Handles SIGTERM/SIGINT properly

## Configuration Management

### Environment Variables
- `REDDIT_CLIENT_ID`: Reddit API credentials
- `REDDIT_CLIENT_SECRET`: Reddit API credentials
- `PG_HOST`, `PG_USER`, `PG_PASSWORD`: Database connection
- `PG_DATABASE`: Database name

### Configuration File (`config.yaml`)
- **Subreddits**: Target communities to scrape
- **Rate Limits**: API request throttling
- **Storage Paths**: CSV file locations
- **Monitoring**: Prometheus and alerting settings
- **Database**: Connection and SQLAlchemy settings

## Monitoring and Observability

### Metrics
- **Prometheus Metrics**: Collection rates, error rates, storage usage
- **Log Files**: Detailed operation logs with rotation
- **Health Checks**: Database connectivity and API status

### Alerting
- **Data Gaps**: Alerts when collection falls behind
- **Error Rates**: Alerts on consecutive API failures
- **Storage Issues**: Disk usage and database connectivity

## Deployment Architecture

### Docker Deployment
- **Base Image**: Python slim with non-root user
- **Volumes**: Data directory for CSV files, logs directory
- **Networks**: Shared network with TimescaleDB and sentiment_analyzer
- **Health Checks**: Built-in health monitoring

### Dependencies
- **TimescaleDB**: Shared database instance
- **Reddit API**: External dependency with rate limits
- **Sentiment Analyzer**: Downstream consumer service

## Performance Considerations

### Scalability
- **Batch Processing**: Configurable batch sizes for database operations
- **Connection Pooling**: SQLAlchemy connection management
- **Async Operations**: Non-blocking API calls with `asyncpraw`

### Resource Usage
- **Memory**: Efficient streaming processing, minimal memory footprint
- **CPU**: Optimized for I/O-bound operations
- **Storage**: Compressed JSON in database, efficient CSV format

## Security Considerations

### Credentials Management
- **Environment Variables**: No hardcoded secrets
- **Reddit API**: OAuth2 with secure token handling
- **Database**: Encrypted connections and proper user permissions

### Data Privacy
- **Public Data**: Only processes publicly available Reddit content
- **No PII**: Avoids collection of personally identifiable information
- **Logging**: Sanitized logs without sensitive data

## Future Enhancements

### Planned Improvements
- **Comment Collection**: Extend to collect Reddit comments
- **Real-time Streaming**: WebSocket-based real-time updates
- **Advanced Filtering**: Content-based filtering before storage
- **Distributed Processing**: Multi-instance deployment support

### Integration Opportunities
- **Additional Sources**: Twitter, news feeds, financial forums
- **Enhanced Analytics**: Real-time sentiment streaming
- **Data Lake Integration**: Long-term archival storage
