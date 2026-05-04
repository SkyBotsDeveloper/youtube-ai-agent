# Scheduling

Phase 7 adds scheduling-ready operations while keeping GitHub Actions as the primary target and VPS cron/manual CLI as secondary options.

## Safe Default

The default daily workflow only generates a script draft:

```bash
python -m raatverse_agent workflow daily-draft --mock
```

It stops for human review. It does not prepare assets, render, prepare upload metadata, or upload video unless later safe flags are explicitly changed and the underlying records are already approved.

Critical defaults:

```env
DAILY_STOP_AFTER_DRAFT=true
AUTO_PREPARE_ASSETS=false
AUTO_RENDER=false
AUTO_PREPARE_UPLOAD=false
AUTO_UPLOAD=false
AUTO_UPLOAD_MUST_BE_APPROVED=true
```

## Workflows

- `daily-draft`: selects a category using strategy, generates a script draft, then stops.
- `full-mock`: runs a safe local mock flow end to end for development.
- `analytics-due`: checks uploads needing 24h, 48h, or 7d snapshots and fetches them.

## Locking

Workflow commands use local lock files under:

```text
./outputs/logs/locks
```

Stale locks are cleared after `SCHEDULER_LOCK_TIMEOUT_MINUTES`.

```env
SCHEDULER_LOCK_ENABLED=true
SCHEDULER_LOCK_TIMEOUT_MINUTES=60
```

## Manual Commands

```bash
python -m raatverse_agent workflow daily-draft --mock
python -m raatverse_agent review queue
python -m raatverse_agent workflow analytics-due --mock
python -m raatverse_agent workflow runs
python -m raatverse_agent workflow status
```
