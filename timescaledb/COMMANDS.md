# TimescaleDB Docker Commands

This file contains useful commands for managing the TimescaleDB Docker container in the Sentiment Pipeline project.

## Container Management

### Start Services
Start all services (TimescaleDB and Reddit Scraper) in detached mode:
```bash
docker-compose up -d
```

### Stop Services
Stop all running services:
```bash
docker-compose down
```

### View Logs
View logs for the TimescaleDB container:
```bash
docker-compose logs -f timescaledb
```

### Access Container Shell
Open an interactive shell in the TimescaleDB container:
```bash
docker-compose exec timescaledb bash
```

## Database Access

### Connect via psql
Connect to the database using psql:
```bash
docker-compose exec timescaledb psql -U test_user -d sentiment_pipeline_db
```

### Run SQL Script
Execute a SQL script from your host machine:
```bash
docker-compose exec -T timescaledb psql -U test_user -d sentiment_pipeline_db < path/to/script.sql
```

## Schema Management

### List All Tables
```bash
docker-compose exec timescaledb psql -U test_user -d sentiment_pipeline_db -c "\dt"
```

### List Hypertables
```bash
docker-compose exec timescaledb psql -U test_user -d sentiment_pipeline_db -c "SELECT * FROM timescaledb_information.hypertables;"
```

### View Table Schema
```bash
docker-compose exec timescaledb psql -U test_user -d sentiment_pipeline_db -c "\d+ raw_events"
```

## Data Operations

### Run a Query
```bash
docker-compose exec timescaledb psql -U test_user -d sentiment_pipeline_db -c "SELECT * FROM raw_events LIMIT 5;"
```

### Count Records in Table
```bash
docker-compose exec timescaledb psql -U test_user -d sentiment_pipeline_db -c "SELECT COUNT(*) FROM raw_events;"
```

### View Chunk Information
View detailed information about hypertable chunks including sizes:
```sql
SELECT 
    c.chunk_name, 
    c.range_start, 
    c.range_end,
    c.is_compressed,
    pg_size_pretty(pg_relation_size(format('%I.%I', c.chunk_schema, c.chunk_name))) as table_size,
    pg_size_pretty(pg_indexes_size(format('%I.%I', c.chunk_schema, c.chunk_name))) as index_size
FROM timescaledb_information.chunks c
WHERE c.hypertable_name = 'raw_events'
ORDER BY c.range_start;
```

### Backup Database
Create a backup:
```bash
docker-compose exec -T timescaledb pg_dump -U test_user sentiment_pipeline_db > backup_$(date +%Y%m%d).sql
```

### Restore Database
```bash
cat backup_file.sql | docker-compose exec -T timescaledb psql -U test_user -d sentiment_pipeline_db
```

## Maintenance

### View Running Queries
```bash
docker-compose exec timescaledb psql -U test_user -d sentiment_pipeline_db -c "SELECT * FROM pg_stat_activity;"
```

### Cancel Running Query
First get the PID from the query above, then:
```bash
docker-compose exec timescaledb psql -U test_user -d sentiment_pipeline_db -c "SELECT pg_cancel_backend(PID);"
```

### View Database Size
```bash
docker-compose exec timescaledb psql -U test_user -d sentiment_pipeline_db -c "SELECT pg_size_pretty(pg_database_size('sentiment_pipeline_db'));"
```

## Troubleshooting

### Check Container Status
```bash
docker-compose ps
```

### View Container Resource Usage
```bash
docker stats $(docker-compose ps -q)
```

### Rebuild and Restart
If you've made changes to the Dockerfile or docker-compose.yml:
```bash
docker-compose up -d --build
```

### Remove All Volumes (WARNING: Deletes all data)
```bash
docker-compose down -v
```

## Alembic Migrations

### Apply Migrations
```bash
docker-compose exec reddit_scraper alembic upgrade head
```

### Create New Migration
```bash
docker-compose exec reddit_scraper alembic revision --autogenerate -m "description of changes"
```

### View Migration History
```bash
docker-compose exec reddit_scraper alembic history
```

### Revert Last Migration
```bash
docker-compose exec reddit_scraper alembic downgrade -1
```
