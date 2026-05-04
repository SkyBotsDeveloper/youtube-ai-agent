# Operations

Phase 9 includes workflow run tracking, locking, review queues, notification hooks, dashboard review-console endpoints, audit logs, and production health checks.

## Workflow Runs

Each operations command writes a `workflow_runs` record with:

- workflow type,
- status,
- start/finish timestamps,
- created draft/asset/render/upload IDs,
- provider mode,
- summary,
- error message.

Commands:

```bash
python -m raatverse_agent workflow runs
python -m raatverse_agent workflow show <run_id>
python -m raatverse_agent workflow status
python -m raatverse_agent ops health
python -m raatverse_agent ops doctor
```

## API

Start FastAPI:

```bash
uvicorn raatverse_agent.api.main:app --reload
```

Check:

- `GET /ops/health`
- `GET /ops/status`
- `GET /ops/workflow-runs`
- `GET /ops/workflow-runs/{id}`
- `POST /ops/run/daily-draft`
- `POST /ops/run/analytics-due`
- `GET /ops/pending-review`
- `GET /review/queue`
- `GET /dashboard`
- `GET /audit/logs`

## Dashboard

`GET /dashboard` returns a lightweight review console with:

- pending approvals,
- script detail links,
- script approve/reject/regenerate actions,
- asset/render/upload metadata preparation actions,
- latest drafts,
- latest renders,
- latest uploads,
- recent workflow runs,
- strategy summary.

It is intentionally lightweight and does not use a frontend framework.

## Failure Recovery

1. Inspect the failed run:

```bash
python -m raatverse_agent workflow show <run_id>
```

2. Check review queue:

```bash
python -m raatverse_agent review queue
```

3. Re-run the safe step after fixing config or credentials:

```bash
python -m raatverse_agent workflow daily-draft --mock
python -m raatverse_agent workflow analytics-due --mock
```

4. If a lock is stale, wait for `SCHEDULER_LOCK_TIMEOUT_MINUTES` or remove the stale file under `outputs/logs/locks`.

## Doctor Checks

`python -m raatverse_agent ops doctor` warns about:

- missing FFmpeg when `VIDEO_RENDERER=ffmpeg`,
- missing real-mode LLM or YouTube credentials,
- dashboard token required but empty,
- unsafe `AUTO_UPLOAD=true`,
- unwritable backup/output directories,
- invalid Postgres configuration,
- production SQLite deployments that need reliable backups.
