# Step-by-step To-Do List

## Project bootstrap

- [ ] Initialise Git repo with conventional commit hooks.
- [ ] Create pyproject.toml (Poetry or Hatch) pinned to Python 3.10.
- [ ] Add pre-commit config for Ruff, Black and MyPy (strict).
- [ ] Write initial README.md stub linking to PRD.

## Secrets & configuration

- [ ] Add .env.example with placeholder Reddit credentials.
- [ ] Draft config.yaml template (subreddits, window_days, paths, etc.).
- [ ] Code a Config dataclass that merges env + YAML.

## Dependency layer

- [ ] Add asyncpraw, pandas, python-dotenv, PyYAML, tqdm, aiohttp.
- [ ] Write thin wrapper reddit_client.py returning an authenticated asyncpraw.Reddit instance.

## Data model

- [ ] Define SubmissionRecord TypedDict with required fields.
- [ ] Create mapping.py to convert asyncpraw.models.Submission → dict.

## Storage layer

- [ ] Implement CsvSink.append(records: list[SubmissionRecord]).
- [ ] Implement CsvSink.load_ids() to seed seen_ids set.
- [ ] Abstract interface so a future ParquetSink drops in.

## Collector core

- [ ] Write collector.latest(subreddit, seen_ids) using .new(limit=None).
- [ ] Write historic search: collector.historic(subreddit, end_epoch, window_days).
- [ ] Integrate rate-limit guard reading X-Ratelimit-Remaining.

## Back-fill engine

- [ ] Build BackfillRunner driving each subreddit until no new ids.
- [ ] Emit progress with tqdm.

## Maintenance loop

- [ ] Build MaintenanceRunner that pulls latest every 600 s.
- [ ] Switch from back-fill to maintenance when cut-off reached.

## Error handling

- [ ] Centralise retry logic with exponential back-off.
- [ ] Abort run after 5 consecutive 5xx responses.

## CLI interface

- [ ] Use typer or argparse for --config, --daemon, --reset-backfill.
- [ ] Wire CLI to start appropriate runner.

## Logging & observability

- [ ] Add logging.conf for rotating file + console.
- [ ] Expose basic metrics JSON (latest fetch age, error counters).

## Unit & integration tests

- [ ] Mock Reddit API with aiohttp test server.
- [ ] Test mapping, deduping, rate-limit handler, sink append.
- [ ] CI workflow: lint ➔ mypy ➔ pytest.

## Docker & deployment

- [ ] Write minimal Dockerfile (python:3.10-slim, non-root).
- [ ] Add docker-compose.yml for local run with mounted volume.
- [ ] Kubernetes CronJob manifest (optional).

## Documentation

- [ ] Flesh out README.md (setup, usage, env vars, monitoring).
- [ ] Add architecture diagram in /docs/.

## Dry-run & acceptance

- [ ] Run back-fill on a single subreddit, verify CSV schema.
- [ ] Time a 10-minute maintenance cycle; ensure duplicates ≤ 0.1 %.
- [ ] Simulate 5xx errors to confirm abort threshold works.

## Production rollout

- [ ] Create S3/GCS bucket or shared volume for CSV storage.
- [ ] Deploy container with secrets, schedule job.
- [ ] Set up alerts on error counters and CSV disk usage.

## Post-launch tasks

- [ ] Monitor for one week; tune window_days and sleep intervals.
- [ ] Plan phase-2: comment harvesting and Parquet migration.
