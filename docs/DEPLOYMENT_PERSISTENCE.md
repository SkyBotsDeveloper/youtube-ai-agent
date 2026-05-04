# Deployment Persistence

Phase 8 keeps SQLite as the default persistence layer and adds backup/export tools for local and VPS deployments.

## Recommended MVP Path

1. Use SQLite on a persistent disk.
2. Keep `DATABASE_URL=sqlite:///./data/raatverse_agent.db`.
3. Run `python -m raatverse_agent db backup` before risky changes.
4. Export JSON snapshots periodically with `python -m raatverse_agent db export-json`.
5. Copy backups outside the app directory.

## VPS

For VPS deployments, keep `data/`, `outputs/backups/`, and `outputs/exports/` on persistent storage. Use cron scripts in `scripts/` for daily draft and analytics due checks.

## GitHub Actions

GitHub-hosted runners are ephemeral. Phase 8 workflows upload the SQLite file and logs as short-retention artifacts for mock/dev inspection only. Artifacts are not the recommended production database.

## Optional Postgres

Postgres can be configured later with `DATABASE_URL`, but it is not required and no Postgres dependency is installed by default. Add a compatible SQLAlchemy driver when moving to Postgres.

## Safety

Persistence changes do not alter upload safety. Auto-upload remains disabled and dashboard actions do not publish videos.
