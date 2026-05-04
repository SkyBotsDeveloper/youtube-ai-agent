# RaatVerse AI YouTube Shorts Agent

Phase 10 of a production-oriented automation system for the YouTube channel **RaatVerse** (`@RaatVerseHindi`).

The project is currently a local-first story draft, asset preparation, local rendering, private YouTube upload, analytics learning, operations orchestration, and review-console system for one original daily Hindi/Hinglish story Short. It supports mock mode, Gemini-compatible script drafts, free-only TTS preparation, stock media metadata planning, local FFmpeg rendering, OAuth setup, private upload workflow, analytics snapshots, category scoring, strategy recommendations, scheduled-safe workflow runs, review queues, a lightweight dashboard, SQLite backup/export/import, Alembic migrations, optional Postgres configuration, approval history, audit export, release operations, deployment runbooks, health/doctor checks, and notification hooks.

## What It Includes

- Free-first design: mock mode works offline, no paid API is required, and real providers are optional.
- Python 3.11+ package with CLI entrypoint.
- Environment-based configuration via Pydantic settings.
- SQLite database with tables for videos, story ideas, analytics snapshots, category scores, and pipeline runs.
- Script draft database and review workflow with `draft`, `approved`, `rejected`, and `needs_revision` statuses.
- Gemini-compatible script generation provider using direct HTTP.
- Prompt templates for horror, mystery, suspense, emotional twist, thriller, urban legend, and psychological stories.
- Safety, duration, CTA, language, and uniqueness validation.
- Free-only narration audio preparation with mock and edge-tts providers.
- Stock media planning with mock, Pexels, and Pixabay providers.
- Asset plans with subtitle timing, scene timing, and source/attribution metadata.
- Local video render workflow with mock and FFmpeg renderers.
- `.ass` high-contrast Shorts subtitles and text watermark support.
- YouTube OAuth helper, metadata preview, upload approval workflow, mock upload, and YouTube Data API private upload adapter.
- YouTube Analytics API provider, mock analytics provider, analytics snapshots, scoring, due-window detection, and learned category recommendations.
- Scheduling-ready workflow orchestration, `workflow_runs`, lock files, GitHub Actions schedules, VPS cron helper scripts, review queue, and lightweight dashboard.
- Dashboard review console actions for script approval/rejection/regeneration, asset prep, render prep, upload metadata prep, and upload approval.
- SQLite backup/restore plus JSON export/import commands; optional Postgres support through `DATABASE_URL`.
- Alembic migration support with SQLite compatibility.
- Backup-before-upgrade flow with `db safe-upgrade`.
- Approval history/comments for review actions.
- Audit logs for dashboard/CLI approval, workflow, upload, import, and restore actions.
- JSON/CSV audit export.
- Release status/checklist/prepare commands.
- Ops health and doctor checks for deployment readiness.
- Production deployment skeletons and runbooks for VPS Docker+Caddy, Windows local, Render, and Railway.
- Mock and generic webhook notification hooks.
- Mock end-to-end pipeline:
  - chooses a story category,
  - generates a mock title and story script,
  - creates mock visual references,
  - creates mock voiceover metadata,
  - creates mock render metadata,
  - creates mock YouTube upload metadata.
- FastAPI skeleton:
  - `GET /health`
  - `GET /pipeline/runs`
  - `POST /pipeline/run-mock`
- Service interfaces for future real providers.
- Tests, Docker skeleton, and GitHub Actions test workflow.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m raatverse_agent db init
python -m raatverse_agent pipeline run --mock
python -m raatverse_agent script generate --category horror --mock
python -m raatverse_agent script approve 1
python -m raatverse_agent tts generate 1 --mock
python -m raatverse_agent assets prepare 1 --mock
python -m raatverse_agent assets quality 1
python -m raatverse_agent render create 1 --mock
python -m raatverse_agent render list
python -m raatverse_agent youtube metadata-preview 1
python -m raatverse_agent youtube prepare-upload 1
python -m raatverse_agent youtube approve-upload 1
python -m raatverse_agent youtube upload 1 --mock
python -m raatverse_agent analytics fetch 1 --mock
python -m raatverse_agent analytics update-scores
python -m raatverse_agent strategy recommend
python -m raatverse_agent script generate --auto-category --mock
python -m raatverse_agent workflow daily-draft --mock
python -m raatverse_agent review queue
python -m raatverse_agent workflow status
python -m raatverse_agent db backup
python -m raatverse_agent db export-json
python -m raatverse_agent db safe-upgrade
python -m raatverse_agent release status
python -m raatverse_agent release checklist
python -m raatverse_agent audit list
python -m raatverse_agent audit export-json
python -m raatverse_agent ops health
python -m raatverse_agent ops doctor
python -m raatverse_agent ops e2e-check --mock
python -m raatverse_agent notify test --mock
python -m raatverse_agent script list
uvicorn raatverse_agent.api.main:app --reload
pytest
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m raatverse_agent db init
python -m raatverse_agent pipeline run --mock
python -m raatverse_agent script generate --category horror --mock
python -m raatverse_agent script approve 1
python -m raatverse_agent tts generate 1 --mock
python -m raatverse_agent assets prepare 1 --mock
python -m raatverse_agent assets quality 1
python -m raatverse_agent render create 1 --mock
python -m raatverse_agent render list
python -m raatverse_agent youtube metadata-preview 1
python -m raatverse_agent youtube prepare-upload 1
python -m raatverse_agent youtube approve-upload 1
python -m raatverse_agent youtube upload 1 --mock
python -m raatverse_agent analytics fetch 1 --mock
python -m raatverse_agent analytics update-scores
python -m raatverse_agent strategy recommend
python -m raatverse_agent script generate --auto-category --mock
python -m raatverse_agent workflow daily-draft --mock
python -m raatverse_agent review queue
python -m raatverse_agent workflow status
python -m raatverse_agent db backup
python -m raatverse_agent db export-json
python -m raatverse_agent db safe-upgrade
python -m raatverse_agent release status
python -m raatverse_agent release checklist
python -m raatverse_agent audit list
python -m raatverse_agent audit export-json
python -m raatverse_agent ops health
python -m raatverse_agent ops doctor
python -m raatverse_agent ops e2e-check --mock
python -m raatverse_agent notify test --mock
python -m raatverse_agent script list
uvicorn raatverse_agent.api.main:app --reload
pytest
```

## Real Gemini-Compatible Script Generation

Set environment variables in `.env`:

```env
LLM_PROVIDER=gemini
LLM_API_KEY=replace-with-your-key
LLM_MODEL=replace-with-gemini-compatible-model
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta
```

Then run:

```bash
python -m raatverse_agent script generate --category horror
```

Real generation creates a saved draft for human review. It does not create voiceover, render video, or upload to YouTube.

## Free TTS and Stock Media

Mock asset workflow:

```bash
python -m raatverse_agent script approve 1
python -m raatverse_agent tts generate 1 --mock
python -m raatverse_agent assets prepare 1 --mock
python -m raatverse_agent assets list
```

## Local Video Rendering

Mock render:

```bash
python -m raatverse_agent render create 1 --mock
```

Real FFmpeg render:

```env
VIDEO_RENDERER=ffmpeg
FFMPEG_BINARY=ffmpeg
RENDER_OUTPUT_DIR=./outputs/renders
```

```bash
python -m raatverse_agent render create 1
```

## YouTube Upload

Mock upload:

```bash
python -m raatverse_agent youtube prepare-upload 1
python -m raatverse_agent youtube approve-upload 1
python -m raatverse_agent youtube upload 1 --mock
```

OAuth setup:

```bash
python -m raatverse_agent youtube oauth-url
python -m raatverse_agent youtube exchange-code <code>
python -m raatverse_agent youtube token-status
```

Real upload is private by default:

```bash
python -m raatverse_agent youtube upload 1
```

## Analytics and Strategy Learning

Mock analytics works without Google credentials:

```bash
python -m raatverse_agent analytics fetch 1 --mock
python -m raatverse_agent analytics update-scores
python -m raatverse_agent strategy recommend
python -m raatverse_agent script generate --auto-category --mock
```

Real analytics uses the official YouTube Analytics API `reports.query` endpoint and OAuth scopes:

```env
YOUTUBE_SCOPES=https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/yt-analytics.readonly https://www.googleapis.com/auth/youtube.readonly
YOUTUBE_ANALYTICS_BASE_URL=https://youtubeanalytics.googleapis.com/v2
```

After changing scopes, delete or revoke the old local token and run the OAuth URL/code exchange again. Analytics only informs future script category strategy; it does not change the private upload approval workflow.

## Scheduling and Operations

Safe daily draft:

```bash
python -m raatverse_agent workflow daily-draft --mock
python -m raatverse_agent review queue
```

Safe full mock development flow:

```bash
python -m raatverse_agent workflow full-mock
```

Analytics due sync:

```bash
python -m raatverse_agent workflow analytics-due --mock
```

Operations API:

```bash
uvicorn raatverse_agent.api.main:app --reload
```

Then check:

- `GET /ops/health`
- `GET /ops/status`
- `GET /audit/logs`
- `GET /review/queue`
- `GET /dashboard`

GitHub Actions scheduled workflows are included under `.github/workflows/` and run mock-safe by default. VPS cron helper scripts are under `scripts/`.

## Dashboard Review Console

Run:

```bash
uvicorn raatverse_agent.api.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/dashboard
```

The dashboard can approve/reject scripts, regenerate rejected scripts, prepare approved assets, create renders, prepare upload metadata, approve upload records, and run safe workflows. It does not include a public upload action.

For remote access, set:

```env
DASHBOARD_REQUIRE_TOKEN=true
DASHBOARD_PROTECT_READS=true
DASHBOARD_ADMIN_TOKEN=replace-with-long-random-token
```

The dashboard includes simple filters/search, approval comments/history, and recent audit logs.

## Migrations and Audit Logs

```bash
python -m raatverse_agent db upgrade
python -m raatverse_agent db safe-upgrade
python -m raatverse_agent db check-migrations
python -m raatverse_agent db current
python -m raatverse_agent db history
python -m raatverse_agent audit list
python -m raatverse_agent audit show <id>
python -m raatverse_agent audit export-json
python -m raatverse_agent audit export-csv
```

`db init` remains available for local MVP use. Use `db safe-upgrade` for VPS/production-style SQLite because it creates a rollback backup before applying migrations.

## Release Operations

```bash
python -m raatverse_agent release status
python -m raatverse_agent release checklist
python -m raatverse_agent release prepare --version 0.1.0
python -m raatverse_agent release notes
python -m raatverse_agent ops e2e-check --mock
```

The E2E check is mock-only and does not call real APIs.

## Backup, Restore, and Notifications

```bash
python -m raatverse_agent db backup
python -m raatverse_agent db backups
python -m raatverse_agent db export-json
python -m raatverse_agent audit export-json
python -m raatverse_agent db import-json <path> --confirm
python -m raatverse_agent db restore <backup_path> --confirm
python -m raatverse_agent db status
python -m raatverse_agent notify test --mock
```

SQLite remains the default database. Postgres is optional through `DATABASE_URL` and is documented for later production deployments.

## Deployment Hardening

Production skeletons:

- `docker-compose.prod.yml`
- `Caddyfile.example`
- `render.yaml`
- `railway.json`
- `scripts/deploy_vps.sh`
- `scripts/backup_cron.sh`
- `scripts/restore_from_backup.sh`

Primary runbook: `docs/DEPLOYMENT_VPS_DOCKER_CADDY.md`.
Windows local runbook: `docs/DEPLOYMENT_WINDOWS_LOCAL.md`.

Run checks:

```bash
python -m raatverse_agent ops health
python -m raatverse_agent ops doctor
python -m raatverse_agent ops e2e-check --mock
```

Free TTS:

```env
TTS_PROVIDER=free
TTS_VOICE=hi-IN-SwaraNeural
TTS_LANGUAGE=hi-IN
TTS_TEXT_MODE=auto
TTS_USE_DEVANAGARI=true
TTS_MAX_CHARS_PER_CHUNK=450
TTS_PAUSE_STYLE=punctuation
```

Pexels/Pixabay:

```env
STOCK_MEDIA_PROVIDER=pexels
PEXELS_API_KEY=replace-with-free-pexels-key
STOCK_MEDIA_AVOID_DUPLICATES=true
STOCK_MEDIA_PREFER_VERTICAL=true
STOCK_MEDIA_MAX_REUSE_PER_URL=1
```

or:

```env
STOCK_MEDIA_PROVIDER=pixabay
PIXABAY_API_KEY=replace-with-free-pixabay-key
```

## Safety Boundaries

The system does not publish public videos automatically and does not store credentials in source control. No paid API is required. YouTube uploads are private by default and require explicit approval. Scheduled daily automation stops after draft generation by default. Analytics uses official APIs only, never scraping. All provider keys and OAuth values are placeholders in `.env.example` and must be supplied through environment variables or ignored local token files.

## Real API Setup Checklist

Use `docs/REAL_API_SETUP_CHECKLIST.md` before enabling real providers. Configure real LLM, free TTS/stock media, YouTube OAuth, and analytics only after the mock E2E check passes:

```bash
python -m raatverse_agent ops e2e-check --mock
```

Keep `AUTO_UPLOAD=false`, `UPLOAD_PRIVACY_STATUS=private`, and `AUTO_UPLOAD_MUST_BE_APPROVED=true`.

## Real Output Quality Workflow

For better real Shorts output, keep Hinglish display narration but send Hindi TTS voices Devanagari-friendly text. Gemini prompts now request `narration_hinglish`, `narration_hindi_devanagari_for_tts`, short subtitle lines, and scene-level stock search fields.

Recommended real render pass:

```bash
python -m raatverse_agent script generate --category horror
python -m raatverse_agent script approve <id>
python -m raatverse_agent tts generate <id>
python -m raatverse_agent assets prepare <id> --download
python -m raatverse_agent assets quality <asset_plan_id>
python -m raatverse_agent render validate <asset_plan_id> --strict-quality
python -m raatverse_agent render create <asset_plan_id>
```

If the asset report shows repeated URLs or weak beats, regenerate assets or improve scene search queries before uploading. Rendering remains local; YouTube upload still requires the existing private, human-approved workflow.
