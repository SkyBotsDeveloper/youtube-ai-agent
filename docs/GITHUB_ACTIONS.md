# GitHub Actions

Phase 8 includes safe scheduled workflows and short-retention mock/dev artifacts:

- `.github/workflows/daily-draft.yml`
- `.github/workflows/analytics-sync.yml`

Both workflows use mock mode by default and do not upload public videos.

## Daily Draft

The daily draft workflow runs at 8:00 PM IST:

```yaml
cron: "30 14 * * *"
```

It runs:

```bash
python -m raatverse_agent db init
python -m raatverse_agent workflow daily-draft --mock
python -m raatverse_agent review queue
```

## Analytics Sync

The analytics sync workflow checks due snapshot windows:

```bash
python -m raatverse_agent workflow analytics-due --mock
python -m raatverse_agent workflow status
```

With GitHub-hosted runners, local SQLite state is ephemeral. Phase 8 uploads the mock/dev SQLite file and logs with `actions/upload-artifact@v4` and `retention-days: 7` for inspection. This is not the recommended production database.

## Secrets for Real Mode Later

Do not commit secrets. Add them as GitHub Actions secrets only when needed:

- `LLM_API_KEY`
- `PEXELS_API_KEY`
- `PIXABAY_API_KEY`
- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`

Real mode should still keep:

```env
AUTO_UPLOAD=false
AUTO_UPLOAD_MUST_BE_APPROVED=true
```

## Manual Run

Both workflows include `workflow_dispatch`, so they can be run manually from the GitHub Actions tab.
