# Production Checklist

Use this before exposing a deployment.

```bash
python -m raatverse_agent release checklist
python -m raatverse_agent db safe-upgrade
python -m raatverse_agent ops doctor
python -m raatverse_agent ops e2e-check --mock
```

Required production values:

```env
APP_ENV=production
AUTO_UPLOAD=false
AUTO_UPLOAD_MUST_BE_APPROVED=true
DASHBOARD_REQUIRE_TOKEN=true
DASHBOARD_PROTECT_READS=true
DASHBOARD_ADMIN_TOKEN=replace-with-long-random-token
DB_BACKUP_BEFORE_UPGRADE=true
RELEASE_BACKUP_REQUIRED=true
AUDIT_LOG_ENABLED=true
```

Recommended:

- HTTPS reverse proxy,
- Caddy or Nginx basic auth,
- backup cron,
- ignored `secrets/` directory,
- regular audit export before upgrades.
