# Persistence

SQLite remains the default local/free MVP database.

```env
DB_ENGINE=sqlite
DATABASE_URL=sqlite:///./data/raatverse_agent.db
```

## Recommended Local/VPS Strategy

1. Keep SQLite on a persistent disk.
2. Run scheduled backups.
3. Export JSON before risky changes.
4. Store backup copies outside the app directory.

## GitHub Actions

GitHub-hosted runners are ephemeral. Phase 8 uploads mock/dev SQLite and logs as artifacts, but artifacts are not the recommended production database.

Use artifacts only for inspection, smoke testing, and mock workflow history.

## Optional Postgres

Postgres is supported through `DATABASE_URL` for future production deployment, but it is not required and no Postgres tests run by default.
