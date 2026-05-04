# Railway Deployment

`railway.json` provides a minimal Docker deployment profile.

## Configure

Set environment variables in Railway:

```env
APP_ENV=production
AUTOMATION_MODE=mock
AUTO_UPLOAD=false
DASHBOARD_REQUIRE_TOKEN=true
DASHBOARD_ADMIN_TOKEN=replace-with-long-random-token
DATABASE_URL=replace-with-persistent-database-url
```

SQLite can work for local or mounted persistent storage, but Railway production deployments should use a persistent database when available. Postgres remains optional.

Do not store OAuth token JSON files in the repo.
