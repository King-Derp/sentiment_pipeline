# Project TODO List

- **Update data ingestion logic to use `RawEventORM`** (Completed: 2025-05-26)
  - Identified `SQLAlchemyPostgresSink` as the component writing Reddit data.
  - Modified `SQLAlchemyPostgresSink` to use `RawEventORM` and map data to the `raw_events` schema.
  - Tested data ingestion successfully.

## Discovered During Work / Next Steps

- **Verify no writes to `raw_submissions` and update downstream consumers** (Added: 2025-05-26)
  - Confirm no active code paths attempt to write to the (now dropped) `raw_submissions` table.
  - Identify and update any downstream processes or queries that previously read from `raw_submissions` to use `raw_events`.
  - Plan for removal of any remaining `SubmissionORM` definitions or related old code if no longer needed.
