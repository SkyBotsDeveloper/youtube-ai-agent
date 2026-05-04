# Architecture

The architecture is intentionally layered so real providers can replace mock providers without changing orchestration code.

## Layers

- `raatverse_agent.config`
  - Loads environment variables and `.env` values through Pydantic settings.
- `raatverse_agent.db`
  - Owns SQLAlchemy models, engine/session setup, and repository methods.
- `raatverse_agent.services.interfaces`
  - Defines provider contracts for scripts, voice, visuals, rendering, thumbnails, YouTube, analytics, and strategy.
- `raatverse_agent.services.mock`
  - Implements deterministic mock providers for local development and tests.
- `raatverse_agent.services.gemini`
  - Implements Gemini-compatible REST script generation for human-review drafts.
- `raatverse_agent.script_generation`
  - Owns script draft schemas, prompt templates, validation, uniqueness checks, and draft orchestration.
- `raatverse_agent.assets`
  - Owns narration audio metadata, subtitle timing, scene timing, stock media metadata, and asset plan orchestration.
- `raatverse_agent.rendering`
  - Owns local mock/FFmpeg rendering, ASS subtitles, watermark filters, render validation, and video render records.
- `raatverse_agent.youtube`
  - Owns OAuth helpers, YouTube metadata generation, private upload workflow, mock uploads, and YouTube Data API upload adapter.
- `raatverse_agent.analytics`
  - Owns mock/real analytics fetching, snapshot scoring, due-window detection, category score updates, and strategy recommendations.
- `raatverse_agent.ops`
  - Owns safe workflow orchestration, local locks, workflow run tracking, review queue summaries, and dashboard helpers.
- `raatverse_agent.pipeline`
  - Coordinates the end-to-end daily Short workflow.
- `raatverse_agent.cli`
  - Provides automation commands such as database initialization and mock pipeline runs.
- `raatverse_agent.api`
  - Exposes a small FastAPI control surface for health checks and mock pipeline runs.

## Current Mock Flow

1. Initialize database tables.
2. Ensure configured story categories exist in `category_scores`.
3. Generate or auto-select a script category.
4. Generate a draft script for human review.
5. Approve the draft.
6. Prepare narration and stock-media asset plan.
7. Render a local video.
8. Prepare, approve, and privately upload in mock or real YouTube mode.
9. Fetch analytics snapshots.
10. Update category scores and strategy recommendations.
11. Track scheduled/manual operations in `workflow_runs`.

## Future Provider Replacement

Each future integration should implement the matching interface:

- `ScriptGenerator`
- `VoiceGenerator`
- `VisualProvider`
- `VideoRenderer`
- `ThumbnailGenerator`
- `YouTubeUploader`
- `AnalyticsFetcher`
- `StrategyAgent`
- `ScriptDraftGenerator`
- `TTSProvider`
- `StockMediaProvider`

The orchestration layer should not directly depend on API SDKs.
