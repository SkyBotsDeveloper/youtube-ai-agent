# Migration Discipline

Before changing SQLAlchemy models:

1. Create a branch.
2. Update models.
3. Generate a migration:

```bash
python -m raatverse_agent db migrate --message "describe change"
```

4. Review the generated file under `raatverse_migrations/versions`.
5. Run:

```bash
python -m raatverse_agent db check-migrations
python -m raatverse_agent db safe-upgrade
python -m pytest
```

SQLite remains supported. Postgres is optional and should be tested separately before production use.
