# Optional Postgres

SQLite remains the default and is the only required database for tests and local mock mode.

## Configure Later

```env
DB_ENGINE=postgres
DATABASE_URL=postgresql+psycopg://user:password@host:5432/raatverse
```

No Postgres driver is required by default. If you set a Postgres `DATABASE_URL` without installing a compatible SQLAlchemy driver, the app raises a clear error asking you to install one or return to SQLite.

## Migrations

Phase 9 adds Alembic migrations. Run:

```bash
python -m raatverse_agent db upgrade
python -m raatverse_agent db current
python -m raatverse_agent db history
```

Postgres remains optional; tests and mock workflows continue to use SQLite by default.

## Recommendation

Use SQLite plus backups for local/VPS MVP. Move to Postgres when:

- multiple machines need the same database,
- dashboard is deployed remotely,
- backups need managed retention,
- concurrent writes become common.
