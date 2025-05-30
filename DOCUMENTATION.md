# Project Documentation Index

This document serves as a central index for all project documentation, organized by category and purpose.

## Root Directory

| File | Purpose |
|------|---------|
| [README.md](./README.md) | Main project overview, setup instructions, and usage guide |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Central document detailing project architecture, data models, component interactions, schema management, configuration, and deployment. |
| [TASK.md](./TASK.md) | Current tasks and their status |
| [TODO.md](./TODO.md) | General to-do items and future work |
| [scraper_implementation_rule.md](./scraper_implementation_rule.md) | Implementation rules and guidelines for scrapers |
| [timescaledb_integration_guide.md](./timescaledb_integration_guide.md) | Comprehensive guide for TimescaleDB integration |

## Common

### Tests
- [timescaledb_test_strategy.md](./common/tests/timescaledb_test_strategy.md) - Consolidated test plan for TimescaleDB integration, combining and optimizing test approaches from multiple sources.

## Reddit Scraper

| File | Purpose |
|------|---------|
| [README.md](./reddit_scraper/README.md) | Main documentation for the Reddit scraper component |
| [prd.md](./reddit_scraper/prd.md) | Product requirements document for the Reddit scraper |
| [todo_part2.md](./reddit_scraper/todo_part2.md) | Additional to-do items for the Reddit scraper (review for consolidation) |
| [test_env.txt](./reddit_scraper/test_env.txt) | Example environment configuration for Reddit scraper tests (review for consolidation) |

### Reddit Scraper Documentation

| File | Purpose |
|------|---------|
| [monitoring.md](./reddit_scraper/docs/monitoring.md) | Monitoring setup and guidelines |
| [pgbouncer_integration_summary.md](./reddit_scraper/docs/pgbouncer_integration_summary.md) | **LEGACY** - PgBouncer integration details (archived) |
| [sqlalchemy_implementation_summary.md](./reddit_scraper/docs/sqlalchemy_implementation_summary.md) | **LEGACY** - SQLAlchemy implementation details (archived) |

## TimescaleDB

| File | Purpose |
|------|---------|
| [COMMANDS.md](./timescaledb/COMMANDS.md) | Useful TimescaleDB commands and queries |
| [prd.md](./timescaledb/prd.md) | Product requirements for TimescaleDB integration |
| [sql_perf_query.md](./timescaledb/sql_perf_query.md) | Performance queries and optimization tips |
| [tests_implementation_plan.md](./timescaledb/tests_implementation_plan.md) | Plan for implementing TimescaleDB tests |
| [todo.md](./timescaledb/todo.md) | Main to-do items for TimescaleDB |
| [todo_details.md](./timescaledb/todo_details.md) | Detailed to-do items and technical debt |

## Documentation Conventions

- `.md` files contain markdown-formatted documentation
- `prd.md` files contain product requirements and specifications
- `todo.md` files track pending work items
- `test_*.md` files contain test plans and strategies

## How to Update This Index

1. When adding new documentation files, update this index
2. Keep the file paths relative to the project root
3. Provide a brief but clear description of each document's purpose
4. Maintain consistent formatting throughout the table
