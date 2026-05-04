# Dashboard

Phase 9 keeps `/dashboard` lightweight but makes it more practical for review operations.

## Run

```bash
uvicorn raatverse_agent.api.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/dashboard
```

## What It Shows

- scripts pending review,
- rejected scripts,
- approved scripts needing assets,
- assets ready for render,
- renders ready for upload metadata,
- uploads pending approval,
- latest analytics snapshots,
- strategy recommendation,
- recent workflow runs,
- recent audit logs.

The dashboard supports simple filters for script status/category/search, upload status, workflow type/status, and audit action/entity type.

## Safe Actions

Dashboard POST actions:

- approve script,
- reject script with reason,
- regenerate rejected script,
- prepare assets for approved script,
- create render from ready asset plan,
- prepare YouTube upload metadata from ready render,
- approve upload record,
- run daily draft workflow,
- run analytics due workflow.

The dashboard intentionally does not include a public upload action. Upload execution still uses the existing explicit upload workflow and private defaults.

## Admin Token

Local dev defaults:

```env
DASHBOARD_ENABLED=true
DASHBOARD_REQUIRE_TOKEN=false
DASHBOARD_PROTECT_READS=false
DASHBOARD_ADMIN_TOKEN=
```

For remote deployments, enable a token:

```env
DASHBOARD_REQUIRE_TOKEN=true
DASHBOARD_PROTECT_READS=true
DASHBOARD_ADMIN_TOKEN=replace-with-long-random-token
DASHBOARD_ALLOWED_HOSTS=your-domain.example
```

Then use:

```text
http://127.0.0.1:8000/dashboard?token=replace-with-long-random-token
```

Production deployments should also use a reverse proxy with HTTPS and authentication.

Dashboard POST actions log audit records when `AUDIT_LOG_ENABLED=true`.
