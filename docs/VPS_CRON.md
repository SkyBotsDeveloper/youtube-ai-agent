# VPS Cron

VPS cron is optional. GitHub Actions is the primary scheduler target, while VPS cron is useful when you want persistent SQLite storage.

## Scripts

Helper scripts:

- `scripts/run_daily_draft.sh`
- `scripts/run_analytics_due.sh`
- `scripts/health_check.sh`

They initialize the database and write logs under:

```text
outputs/logs
```

## Crontab Examples

Daily 8:00 PM IST draft generation:

```cron
TZ=Asia/Kolkata
0 20 * * * cd /path/to/youtube-ai-agent && bash scripts/run_daily_draft.sh
```

Analytics sync twice daily:

```cron
TZ=Asia/Kolkata
30 8,21 * * * cd /path/to/youtube-ai-agent && bash scripts/run_analytics_due.sh
```

Health check:

```cron
TZ=Asia/Kolkata
*/30 * * * * cd /path/to/youtube-ai-agent && bash scripts/health_check.sh >> outputs/logs/health.log 2>&1
```

## Notes

- Use `python -m venv .venv` and install dependencies before enabling cron.
- Keep `.env` local to the VPS and never commit it.
- Back up SQLite with `python -m raatverse_agent db backup`.
- Export JSON with `python -m raatverse_agent db export-json` before risky changes.
- Use `tmux`, `systemd`, or a process manager later only if you need long-running services.
- The scheduler lock prevents duplicate local workflow runs.
