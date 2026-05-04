# Migrations

Phase 9 adds Alembic support while keeping `python -m raatverse_agent db init` available for the local SQLite MVP.

## Commands

```bash
python -m raatverse_agent db upgrade
python -m raatverse_agent db safe-upgrade
python -m raatverse_agent db check-migrations
python -m raatverse_agent db current
python -m raatverse_agent db history
python -m raatverse_agent db migrate --message "describe schema change"
```

`db upgrade` applies migrations to `DATABASE_URL`. `db safe-upgrade` creates a SQLite backup first and is the recommended production-style command.

## Current Setup

- `alembic.ini` points to `raatverse_migrations`.
- `raatverse_migrations/versions/0001_initial_schema.py` represents the current Phase 1-9 schema.
- The initial migration uses SQLAlchemy metadata so existing SQLite databases can be marked at the initial revision without dropping local data.

## Local MVP

For local development, this still works:

```bash
python -m raatverse_agent db init
```

Use migrations before moving a long-running deployment to Postgres or when schema changes become non-trivial.
