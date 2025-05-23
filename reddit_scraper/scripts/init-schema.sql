-- PostgreSQL initialization script for Reddit Finance Scraper
-- Creates the necessary schema and partitioning setup

-- Helper function to create date partitions
CREATE OR REPLACE FUNCTION create_partition_for_date(
    partition_date DATE
) RETURNS VOID AS $$
DECLARE
    partition_name TEXT;
    partition_start TEXT;
    partition_end TEXT;
    year_month_day TEXT;
BEGIN
    -- Format as YYYY_MM_DD for partition name
    year_month_day := TO_CHAR(partition_date, 'YYYY_MM_DD');
    partition_name := 'raw_events_' || year_month_day;
    
    -- Format as ISO strings for partition bounds
    partition_start := partition_date::TEXT;
    partition_end := (partition_date + INTERVAL '1 day')::TEXT;
    
    -- Create partition if it doesn't exist
    EXECUTE FORMAT('
        CREATE TABLE IF NOT EXISTS %I
        PARTITION OF raw_events
        FOR VALUES FROM (%L) TO (%L)
    ', partition_name, partition_start, partition_end);
    
    RAISE NOTICE 'Created partition % for date %', partition_name, partition_date;
END;
$$ LANGUAGE plpgsql;

-- Main raw_events table with partitioning
CREATE TABLE IF NOT EXISTS raw_events (
  id            BIGSERIAL     NOT NULL,
  source        TEXT          NOT NULL,
  source_id     TEXT          NOT NULL,
  occurred_at   TIMESTAMPTZ   NOT NULL,
  payload       JSONB         NOT NULL,
  created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  processed     BOOLEAN       NOT NULL DEFAULT FALSE,
  PRIMARY KEY (id, occurred_at),
  UNIQUE (source_id, occurred_at)
) PARTITION BY RANGE (occurred_at);

-- Unique constraint is already added in the table definition with (source_id, occurred_at)

-- Create indexes on the parent table (will be inherited by partitions)
CREATE INDEX IF NOT EXISTS idx_raw_events_source_occurred_at 
ON raw_events (source, occurred_at);

CREATE INDEX IF NOT EXISTS idx_raw_events_payload 
ON raw_events USING GIN (payload);

-- Create initial partitions for current date and +/- 3 days
DO $$
DECLARE
    current_date DATE := CURRENT_DATE;
    i INT;
BEGIN
    -- Create partitions for past 3 days, today, and next 3 days
    FOR i IN -3..3 LOOP
        PERFORM create_partition_for_date(current_date + i);
    END LOOP;
END $$;

-- Function to automatically create daily partitions
CREATE OR REPLACE FUNCTION create_raw_events_partition_for_tomorrow() 
RETURNS VOID AS $$
DECLARE
    tomorrow DATE := CURRENT_DATE + INTERVAL '1 day';
BEGIN
    PERFORM create_partition_for_date(tomorrow);
END;
$$ LANGUAGE plpgsql;

-- Create a scheduled job to run the daily partition creation
DO $$
BEGIN
    -- Check if pg_cron extension is available
    IF EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'pg_cron'
    ) THEN
        -- Schedule job to create partition for tomorrow (runs daily at 00:05)
        PERFORM cron.schedule('5 0 * * *', 'SELECT create_raw_events_partition_for_tomorrow()');
        RAISE NOTICE 'Scheduled automatic partition creation using pg_cron';
    ELSE
        RAISE NOTICE 'pg_cron extension not available - automatic partition creation will not be scheduled';
        RAISE NOTICE 'To enable automatic partition creation, install pg_cron or create a cron job outside PostgreSQL';
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Error setting up automatic partition creation: %', SQLERRM;
END $$;
