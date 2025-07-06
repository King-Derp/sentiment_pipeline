# Power BI Integration Guide

This document describes how to set up and configure Power BI integration with the Sentiment Pipeline, supporting both real-time streaming and historical analysis.

**Version:** 1.1  
**Date:** 2025-07-06

## Overview

The sentiment analyzer service provides a hybrid Power BI integration that combines:

1. **Real-time streaming** via Power BI's Push API for live dashboards
2. **Historical analysis** via DirectQuery to TimescaleDB for comprehensive reporting

This dual approach provides the best of both worlds: real-time visibility and deep historical analysis.

## Architecture

```
┌─────────────────┐    ┌───────────────────┐    ┌─────────────────────┐
│  Sentiment     │    │  Result          │    │  Power BI          │
│  Pipeline      │───▶│  Processor       │───▶│  Streaming Dataset  │
└─────────────────┘    └───────────────────┘    └──────────┬──────────┘
                                                           │
                                                           ▼
┌─────────────────┐    ┌───────────────────┐    ┌─────────────────────┐
│  TimescaleDB    │◀───│  DirectQuery     │◀───│  Power BI           │
│  (Historical)   │    │  Connection      │    │  Historical Reports │
└─────────────────┘    └───────────────────┘    └─────────────────────┘
```

### Components

1. **PowerBI Client** (`sentiment_analyzer/integrations/powerbi.py`)
   - Async client with batching and retry logic
   - Handles rate limiting and connection failures
   - Converts sentiment results to Power BI compatible format
   - Implements exponential backoff for retries
   - Supports both real-time push and historical query operations

2. **Result Processor Integration**
   - Automatically streams results after successful database save
   - Non-blocking operation (doesn't fail if Power BI is unavailable)
   - Converts ORM objects to DTOs for streaming
   - Maintains data consistency between real-time and historical views

3. **DirectQuery Integration**
   - Direct connection to TimescaleDB for historical reporting
   - Supports complex analytical queries
   - Enables combining real-time and historical data in the same reports

## Power BI Setup

### 1. Create a Streaming Dataset

1. **Log into Power BI Service** (app.powerbi.com)
2. **Navigate to your workspace**
3. **Create a new streaming dataset:**
   - Go to "Datasets" → "Create" → "Streaming dataset"
   - Choose "API" as the source
   - Define the schema (see schema below)
   - **Enable "Historic data analysis"** to store data for historical reporting
   - Copy the **Push URL** for configuration

### 2. Configure DirectQuery to TimescaleDB

1. **Set up database access:**
   - Ensure the TimescaleDB instance is reachable by an on-premises data gateway
   - Create a read-only database role with minimal `SELECT` privileges
   - (Optional) Create SQL views or materialized views for common queries (e.g., `sentiment_metrics_daily`)

2. **In Power BI Desktop:**
   - Select *Get Data* → *PostgreSQL*
   - Choose *DirectQuery* connection type
   - Configure the gateway connection with read-only credentials
   - Import or create necessary SQL views

### 3. Dataset Schema

The streaming dataset should have the following fields:

| Field Name | Data Type | Description |
|------------|-----------|-------------|
| `event_id` | Text | Unique identifier for the event |
| `timestamp` | DateTime | When the event occurred (use as primary date/time field) |
| `source` | Text | Source of the event (e.g., "reddit", "twitter") |
| `source_id` | Text | Source-specific identifier |
| `sentiment_score` | Decimal | Numerical sentiment score (-1.0 to 1.0) |
| `sentiment_label` | Text | Sentiment category ("positive", "negative", "neutral") |
| `confidence` | Decimal | Confidence score (0.0 to 1.0) |
| `model_version` | Text | Version of the sentiment analysis model used |
| `raw_text` | Text | The original, unprocessed text of the event |

> **Note:** The field names must match exactly between your Power BI dataset and the data being sent from the application.

### 4. Build a Composite Dashboard

1. **Create a new report** in Power BI Desktop
2. **Add the streaming dataset** as a live connection
3. **Add DirectQuery tables/views** for historical data
4. **Create a date dimension table** and relate it to your time-based data

#### Recommended Visuals

**Real-time Tiles (using streaming dataset):**
- Real-time sentiment distribution (pie/donut chart)
- Sentiment trends (line chart, last 15-60 minutes)
- Latest sentiment scores (table/cards)
- Source breakdown (bar/column chart)

**Historical Analysis (using DirectQuery):**
- Sentiment trends by day/week/month (line/area chart)
- Sentiment distribution by source (stacked bar/column)
- Sentiment correlation with other metrics (scatter plot)
- Top/bottom performing content (table with sentiment scores)

**Composite Visuals (combining real-time and historical):**
- Dashboard with real-time metrics alongside historical context
- Time-series showing current period vs. previous period
- Anomaly detection comparing current sentiment to historical patterns

## Configuration

### Environment Variables

Add the following variables to your `.env` file:

```bash
# Power BI Integration
POWERBI_PUSH_URL=https://api.powerbi.com/beta/[workspace-id]/datasets/[dataset-id]/rows?[key]
POWERBI_API_KEY=optional_api_key_if_required

# Database Connection for DirectQuery (use read-only credentials)
PG_HOST=timescaledb
PG_PORT=5432
PG_DB=sentiment_pipeline_db
PG_USER=powerbi_user
PG_PASSWORD=your_secure_password
```

### Settings

The configuration is automatically loaded through the settings system:

```python
# In sentiment_analyzer/config/settings.py

# Power BI Settings
POWERBI_PUSH_URL: Optional[str] = None
POWERBI_API_KEY: Optional[str] = None
POWERBI_MAX_RETRIES: int = 3
POWERBI_RETRY_DELAY: float = 1.0
POWERBI_BATCH_SIZE: int = 100

# Database Settings (for DirectQuery)
PG_HOST: str = "timescaledb"
PG_PORT: int = 5432
PG_DB: str = "sentiment_pipeline_db"
PG_USER: str = "powerbi_user"
PG_PASSWORD: str = ""
```

## Usage

### Automatic Streaming

Once configured, the system automatically handles both real-time and historical data:

1. **Raw events** are processed through the sentiment pipeline
2. **Results are saved** to TimescaleDB via `ResultProcessor`
3. **PowerBI streaming** happens automatically after successful save
4. **Batching and retry logic** handle rate limits and failures
5. **Historical data** is available immediately via DirectQuery

### Manual Operations

You can also interact with the PowerBI client directly:

```python
from sentiment_analyzer.integrations.powerbi import PowerBIClient
from sentiment_analyzer.models.dtos import SentimentResultDTO

# Initialize client with settings
client = PowerBIClient(
    push_url=settings.POWERBI_PUSH_URL,
    api_key=settings.POWERBI_API_KEY,
    max_retries=settings.POWERBI_MAX_RETRIES,
    retry_delay=settings.POWERBI_RETRY_DELAY,
    batch_size=settings.POWERBI_BATCH_SIZE
)

# Stream a single result
result_dto = SentimentResultDTO(...)
await client.push_row(result_dto)

# Stream multiple results with batching
results = [result_dto1, result_dto2, ...]
await client.push_rows(results)

# Test connection to Power BI
is_connected = await client.test_connection()

# Get current batch queue size
queue_size = client.queue_size

# Force flush any batched data
await client.flush()
```

### Hybrid Query Example

To combine real-time and historical data in a single report:

1. **Create a date dimension table** in your DirectQuery model
2. **Create a relationship** between your date dimension and both:
   - The streaming dataset's `timestamp` field
   - The historical data's timestamp field
3. **Use measures** to combine data from both sources:
   ```dax
   Combined Sentiment = 
   IF(
       ISFILTERED('Real-time Data'[timestamp]),
       AVERAGE('Real-time Data'[sentiment_score]),
       AVERAGE('Historical Data'[sentiment_score])
   )
   ```

## Features

### Hybrid Architecture
- Combines real-time streaming with historical analysis
- Real-time data via Power BI Push API
- Historical data via DirectQuery to TimescaleDB
- Unified reporting experience across time horizons

### Batching
- Results are batched for efficiency (default: 100 rows per batch)
- Configurable batch size via client initialization
- Automatic flushing on shutdown or when batch size is reached
- Memory-efficient queue management

### Retry Logic
- Exponential backoff for transient failures
- Special handling for rate limiting (HTTP 429)
- Configurable max retries and delay
- Circuit breaker pattern to prevent cascading failures

### Error Handling
- Non-blocking operation (doesn't fail sentiment processing)
- Comprehensive logging for monitoring
- Graceful degradation when Power BI is unavailable
- Dead-letter queue for failed messages

### Performance
- Async/await throughout for non-blocking operations
- Connection pooling via httpx
- Efficient JSON serialization
- Optimized for high throughput with minimal overhead

## Monitoring and Maintenance

### Logs

The PowerBI integration provides detailed logging at various levels:

```
# Normal operation
INFO: Streamed sentiment result to PowerBI for event_id: 123

# Warnings (investigate but not critical)
WARNING: PowerBI rate limit approached, backing off...
WARNING: PowerBI connection slow, current batch took 2.1s

# Debug information
DEBUG: PowerBI batch flushed: 50 rows sent successfully
DEBUG: PowerBI client initialized with batch size 100

# Errors (requires attention)
ERROR: Failed to stream result to PowerBI for event_id 456: 429 Too Many Requests
```

### Health Checks

Monitor the health of your integration:

```python
from sentiment_analyzer.integrations.powerbi import powerbi_client

# Test connection to Power BI
is_connected = await powerbi_client.test_connection()

# Check queue status
queue_status = {
    'queue_size': powerbi_client.queue_size,
    'last_success': powerbi_client.last_success,
    'last_error': powerbi_client.last_error,
    'total_sent': powerbi_client.metrics['total_sent'],
    'total_failed': powerbi_client.metrics['total_failed']
}

# Test database connectivity (for DirectQuery)
from sentiment_analyzer.db.session import get_db_session
async with get_db_session() as session:
    is_db_connected = await session.execute("SELECT 1")
```

### Performance Metrics

Track these key metrics:
- **Latency**: Time from event processing to dashboard update
- **Throughput**: Events processed per second
- **Error rate**: Percentage of failed transmissions
- **Queue size**: Number of events waiting to be sent
- **Retry count**: Number of retries per failed transmission

## Troubleshooting

### Common Issues

#### Push API Issues
1. **Invalid Push URL**
   - Verify the URL format and dataset ID
   - Ensure the dataset exists and is accessible
   - Check if the dataset has been deleted and recreated (URL changes)

2. **Rate Limiting (HTTP 429)**
   - Power BI has rate limits (typically 1M rows/hour)
   - The client automatically retries with exponential backoff
   - Solutions:
     - Reduce batch size
     - Increase retry delay
     - Implement client-side throttling if needed

3. **Schema Mismatches**
   - Ensure the dataset schema matches the data being sent
   - Check field names, data types, and required fields
   - Verify date/time formats match Power BI's expectations

4. **Authentication Issues**
   - Verify API keys are correct and have not expired
   - Check workspace permissions and access levels
   - Ensure the service principal has required permissions

#### DirectQuery Issues
1. **Gateway Connection Failures**
   - Verify the on-premises data gateway is running
   - Check network connectivity between gateway and database
   - Validate database credentials and permissions

2. **Query Performance**
   - Large datasets may require query optimization
   - Consider creating materialized views for common queries
   - Use appropriate indexes on frequently filtered columns

3. **Data Freshness**
   - Configure appropriate refresh intervals
   - Consider using incremental refresh for large datasets
   - Monitor gateway resource usage

### Debug Mode

Enable debug logging to see detailed operations:

```python
import logging

# Enable debug logging for PowerBI client
logging.getLogger("sentiment_analyzer.integrations.powerbi").setLevel(logging.DEBUG)

# For HTTP request/response details
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("httpcore").setLevel(logging.DEBUG)

# For database queries
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)  # Set to DEBUG for SQL queries
```

### Getting Help

When seeking support, include:
1. Relevant log entries (with timestamps)
2. The error message and stack trace
3. Sample of the data being sent (redact sensitive information)
4. Power BI dataset configuration
5. Database schema and query plans (for DirectQuery issues)

## Best Practices

### General
1. **Monitor Usage**: Track Power BI API usage and database query performance
2. **Graceful Degradation**: Ensure system remains functional if Power BI is unavailable
3. **Data Retention**: Implement appropriate data retention policies for both real-time and historical data

### Security
1. **Least Privilege**: Use read-only database users for DirectQuery
2. **Secret Management**: Store credentials in environment variables or a secure vault
3. **Network Security**: Use private endpoints and VPC peering where possible
4. **Audit Logging**: Monitor access to sensitive data and operations

### Performance
1. **Batch Sizes**: Optimize batch sizes based on your workload (larger batches = better throughput but higher memory usage)
2. **Query Optimization**: Use appropriate indexes and materialized views for historical queries
3. **Caching**: Implement caching for frequently accessed historical data
4. **Partitioning**: Partition large tables by time for better query performance

### Maintenance
1. **Regular Testing**: Periodically test failover and recovery procedures
2. **Version Control**: Keep Power BI reports and data models in version control
3. **Documentation**: Maintain up-to-date documentation of your data model and integration points
4. **Monitoring**: Set up alerts for error conditions and performance degradation

## Conclusion

This hybrid Power BI integration provides a powerful combination of real-time monitoring and historical analysis. By following the guidelines in this document, you can create comprehensive dashboards that provide both immediate insights and long-term trend analysis.

For additional assistance, refer to:
- [Power BI Documentation](https://docs.microsoft.com/en-us/power-bi/)
- [TimescaleDB Documentation](https://docs.timescale.com/)
- [Project Documentation](../sentiment_docs/)

Happy dashboarding!
3. **Use Appropriate Batch Sizes**: Balance between efficiency and memory usage
4. **Test Connectivity**: Regularly verify PowerBI connection health
5. **Schema Versioning**: Plan for schema changes in your datasets

## Security Considerations

1. **Secure URLs**: Keep PowerBI push URLs confidential
2. **Environment Variables**: Never commit credentials to version control
3. **Network Security**: Ensure HTTPS connections to Power BI
4. **Access Control**: Limit who can access PowerBI workspaces and datasets

## Performance Tuning

### Batch Size Optimization
```python
# For high-volume scenarios
client = PowerBIClient(
    push_url=url,
    batch_size=500,  # Larger batches for efficiency
    max_retries=3,   # More retries for reliability
    retry_delay=2.0  # Longer delays for rate limiting
)
```

### Memory Management
- Monitor memory usage with large batches
- Consider flushing batches more frequently for memory-constrained environments

## Integration with Composite Models

For advanced Power BI setups using composite models:

1. **Create a streaming dataset** for real-time data
2. **Create a DirectQuery dataset** for historical data from your database
3. **Combine both** in a composite model for comprehensive analytics
4. **Use measures** to blend real-time and historical data

This approach provides both real-time streaming and historical analysis capabilities.
