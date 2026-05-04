# VPS Deployment

VPS deployment is optional. GitHub Actions mock/dev workflows remain supported, but a persistent host is better for real SQLite data.

## Recommended Layout

- app repo under `/opt/raatverse-agent`,
- `.env` owned by the deploy user,
- SQLite DB in `data/`,
- backups in `outputs/backups`,
- exports in `outputs/exports`,
- token files in `secrets/`.

## Deploy

```bash
scripts/deploy_vps.sh
```

## Backups

```bash
scripts/backup_cron.sh
```

Crontab example:

```cron
15 2 * * * cd /opt/raatverse-agent && scripts/backup_cron.sh >> outputs/logs/backup.log 2>&1
```

## Restore

```bash
scripts/restore_from_backup.sh outputs/backups/<backup>.sqlite3
```

Keep `AUTO_UPLOAD=false` and require dashboard token protection when the dashboard is reachable remotely.
