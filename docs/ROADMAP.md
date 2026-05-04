# Roadmap

## Phase 1: Foundation

Completed scope:

- Repository structure.
- Config management.
- SQLite schema.
- Service interfaces.
- Mock pipeline.
- CLI and FastAPI skeleton.
- Tests and docs.

## Phase 2: Real Story Generation and Approval Drafts

Completed scope:

- Add a real LLM-backed `ScriptGenerator` with Gemini-compatible configuration.
- Add prompt templates for Hindi/Hinglish horror, mystery, suspense, and emotional twist Shorts.
- Add uniqueness checks against existing `videos` and `story_ideas`.
- Add a draft review artifact for human approval before rendering or upload.
- Add stronger validation for duration, language, CTA presence, and originality.

## Phase 3: Media and Voice

Completed scope:

- Add TTS provider integration.
- Add stock media search adapters for free/limited-free APIs.
- Add asset caching and attribution tracking.
- Add audio timing metadata.
- Add manual revision/regeneration workflow for rejected drafts.

## Phase 4: Rendering

Completed scope:

- Add FFmpeg-based vertical 1080x1920 renderer.
- Add subtitle rendering.
- Add brand styling presets.
- Add local preview generation.
- Use approved `AssetPlan` records as the rendering input.

## Phase 5: YouTube Upload and Scheduling

Completed scope:

- Add OAuth setup flow.
- Upload privately by default.
- Add optional scheduled publish time.
- Store YouTube video IDs.
- Require explicit human approval before public scheduling.

## Phase 6: Analytics and Learning

Completed scope:

- Fetch YouTube analytics snapshots.
- Update category scores.
- Track retention and engagement.
- Use strategy logic to choose future categories responsibly.

## Phase 7: Scheduler and Operations

Completed scope:

- Add a scheduler for daily one-video automation checkpoints.
- Run analytics due checks for 24h, 48h, and 7d windows.
- Add job locking and retry policy.
- Add dashboard views for drafts, renders, uploads, analytics, and strategy.
- Keep human approval gates before upload and publishing.

## Phase 8: Dashboard UX and Persistent Deployment

Completed scope:

- Add a fuller local dashboard for review and approval actions.
- Add persistent deployment guidance for Railway/Render/VPS with SQLite backup or Postgres.
- Add artifact persistence for GitHub Actions or move scheduled jobs to a persistent host.
- Add notification hooks for draft/review failures.

## Phase 9: Deployment Hardening

Completed scope:

- Add Alembic migrations with SQLite compatibility and optional Postgres readiness.
- Add stronger dashboard token behavior and optional read protection.
- Add audit logs for approval, workflow, upload, import, and restore actions.
- Add dashboard filtering/search for review operations.
- Add Docker/VPS/Render/Railway deployment profiles and production security docs.
- Add ops health and doctor checks.

## Phase 10: Release Operations and Quality Gates

Completed scope:

- Add Alembic migration discipline for every future schema change.
- Add release checklist and versioned backups before upgrades.
- Add dashboard audit-log export and richer approval comments.
- Add approval event history.
- Add VPS Docker+Caddy and Windows local deployment runbooks.
- Add final mock E2E readiness check.

## Future Real Setup

Recommended next work:

- Configure real Gemini-compatible LLM credentials.
- Configure free TTS and stock media providers.
- Complete YouTube OAuth on the target channel.
- Run private uploads only after manual approval.
- Harden dashboard access with reverse proxy auth before remote exposure.
