# Upgrade and Rollback

Use `safe-upgrade` for SQLite deployments.

```bash
python -m raatverse_agent db safe-upgrade
```

This flow:

- checks migration status,
- creates a timestamped SQLite backup when the DB file exists,
- runs Alembic upgrade,
- verifies DB health,
- prints the rollback command.

Rollback example:

```bash
python -m raatverse_agent db restore outputs/backups/<backup>.sqlite3 --confirm
```

For VPS Docker deployments, stop the container before restoring if the app is actively writing to SQLite.
