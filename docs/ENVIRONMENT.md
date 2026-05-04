# Environment

All runtime configuration is loaded from environment variables. Use `.env.example` as the template and create a local `.env` file.

## Core

- `APP_VERSION`: Release/version display value.
- `APP_ENV`: Runtime environment name.
- `LOG_LEVEL`: Logging verbosity.
- `DATABASE_URL`: SQLAlchemy database URL. Defaults to local SQLite.

## Channel

- `CHANNEL_NAME`: YouTube channel name.
- `YOUTUBE_CHANNEL_HANDLE`: YouTube handle.
- `DEFAULT_TIMEZONE`: Scheduling timezone.
- `DAILY_UPLOAD_TIME`: Planned daily upload time.
- `HUMAN_APPROVAL_REQUIRED`: Keeps upload flow review-first.
- `UPLOAD_PRIVACY_STATUS`: Default future upload privacy. Use `private` for approval workflows.
- `STORY_CATEGORIES_CSV`: Comma-separated strategy categories.
- `SCRIPT_CATEGORIES_CSV`: Comma-separated script generation categories.
- `LANGUAGE_STYLE`: Default narration language style.
- `MIN_VIDEO_SECONDS`: Lower bound for Shorts duration.
- `MAX_VIDEO_SECONDS`: Upper bound for Shorts duration.
- `SCRIPT_MIN_WORDS`: Lower bound for generated narration length.
- `SCRIPT_MAX_WORDS`: Upper bound for generated narration length.
- `SCRIPT_SIMILARITY_THRESHOLD`: Similarity threshold for rejecting repetitive scripts.
- `SCRIPT_RECENT_WINDOW`: Number of recent records used for repetition checks.
- `SCRIPT_MAX_RECENT_SAME_CATEGORY_STORY_TYPE`: Warning threshold for repeated category/story-type usage.
- `SCRIPT_EXPLOITATION_RATE`: Placeholder exploitation share for analytics-aware category preference.
- `SCRIPT_GENERATION_MAX_ATTEMPTS`: Number of generation attempts before saving a draft with issues.
- `OUTRO_CTA`: Standard RaatVerse outro call to action.

## Future Providers

- `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_TIMEOUT_SECONDS`, `LLM_TEMPERATURE`: Script generation provider settings.
- `TTS_PROVIDER`: `mock`, `free`, `edge-tts`, or future `local`.
- `TTS_VOICE`: Voice preset such as `female_hindi`.
- `TTS_LANGUAGE`: Narration language, default `hi-IN`.
- `TTS_SPEAKING_RATE`: `slow`, `normal`, `fast`, or edge-tts percentage.
- `TTS_OUTPUT_FORMAT`: Audio extension, default `mp3`.
- `TTS_MAX_RETRIES`: Free TTS retry count.
- `TTS_CACHE_DIR`: Local narration output directory.
- `STOCK_MEDIA_PROVIDER`: `mock`, `pexels`, `pixabay`, or `both`.
- `PEXELS_API_KEY`: Free Pexels API key for stock search.
- `PIXABAY_API_KEY`: Free Pixabay API key for stock search.
- `STOCK_MEDIA_RESULTS_PER_BEAT`: Number of media candidates per scene beat.
- `STOCK_MEDIA_CACHE_DIR`: Local media cache directory.
- `STOCK_MEDIA_DOWNLOAD_ENABLED`: Enables optional media downloads. Default is `false`.
- `STOCK_MEDIA_TIMEOUT_SECONDS`: HTTP timeout for stock media providers.
- `FFMPEG_BINARY`, `OUTPUT_DIR`: Rendering settings.
- `VIDEO_RENDERER`: `mock` or `ffmpeg`.
- `RENDER_OUTPUT_DIR`: Local render output directory.
- `RENDER_WIDTH`: Render width, default `1080`.
- `RENDER_HEIGHT`: Render height, default `1920`.
- `RENDER_FPS`: Render FPS, default `30`.
- `RENDER_VIDEO_CODEC`: FFmpeg video codec, default `libx264`.
- `RENDER_AUDIO_CODEC`: FFmpeg audio codec, default `aac`.
- `RENDER_PRESET`: FFmpeg preset, default `veryfast`.
- `RENDER_CRF`: FFmpeg CRF quality value, default `23`.
- `RENDER_MOCK_ENABLED`: Enables mock rendering.
- `WATERMARK_ENABLED`: Enables text watermark.
- `WATERMARK_TEXT`: Watermark text.
- `WATERMARK_POSITION`: `top-right`, `top-left`, `bottom-right`, or `bottom-left`.
- `SUBTITLE_STYLE`: Subtitle style preset, default `shorts_high_contrast`.
- `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`, `YOUTUBE_TOKEN_URI`, `YOUTUBE_SCOPES`: YouTube OAuth settings.
- `YOUTUBE_REDIRECT_URI`: OAuth redirect URI configured in Google Cloud Console.
- `YOUTUBE_TOKEN_FILE`: Ignored local token file path.
- `YOUTUBE_CATEGORY_ID`: YouTube category ID, default `24`.
- `YOUTUBE_DEFAULT_LANGUAGE`: Metadata language, default `hi`.
- `YOUTUBE_CONTAINS_SYNTHETIC_MEDIA`: Whether uploads disclose synthetic media by default.
- `YOUTUBE_SELF_DECLARED_MADE_FOR_KIDS`: Audience setting, default `false`.
- `YOUTUBE_DEFAULT_SCHEDULE_TIME`: Default scheduled publish time, default `20:00`.
- `ANALYTICS_FETCH_ENABLED`: Legacy flag for analytics fetching.
- `YOUTUBE_ANALYTICS_ENABLED`: Enables real YouTube Analytics workflows when credentials are configured.
- `YOUTUBE_ANALYTICS_BASE_URL`: YouTube Analytics API base URL.
- `ANALYTICS_DEFAULT_WINDOWS`: Comma-separated snapshot windows, default `24h,48h,7d`.
- `ANALYTICS_WEIGHT_VIEWS`: Performance-score weight for views.
- `ANALYTICS_WEIGHT_LIKE_RATE`: Performance-score weight for like rate.
- `ANALYTICS_WEIGHT_COMMENT_RATE`: Performance-score weight for comment rate.
- `ANALYTICS_WEIGHT_RETENTION`: Performance-score weight for average view duration retention.
- `ANALYTICS_WEIGHT_SUBSCRIBERS`: Performance-score weight for subscribers gained.
- `ANALYTICS_EARLY_WINDOW_WEIGHT`: Category-score weight for early 24h/48h performance.
- `ANALYTICS_SEVEN_DAY_WEIGHT`: Category-score weight for stable 7-day performance.
- `STRATEGY_EXPLOITATION_RATE`: Share of weekly recommendations for proven categories.
- `STRATEGY_EXPLORATION_RATE`: Share of weekly recommendations for variety/new categories.
- `AUTOMATION_MODE`: `mock` or `real`; defaults to `mock`.
- `DAILY_DRAFT_ENABLED`: Enables scheduled daily draft workflow.
- `DAILY_DRAFT_TIME`: Human target time for the daily workflow.
- `SCHEDULER_TIMEZONE`: Scheduler display/timezone setting.
- `DAILY_AUTO_CATEGORY`: Uses strategy scores for daily category selection.
- `DAILY_STOP_AFTER_DRAFT`: Stops automation after draft generation. Default `true`.
- `AUTO_PREPARE_ASSETS`: Disabled by default.
- `AUTO_RENDER`: Disabled by default.
- `AUTO_PREPARE_UPLOAD`: Disabled by default.
- `AUTO_UPLOAD`: Disabled by default.
- `CONFIRM_ENABLE_AUTO_UPLOAD`: Must be `true` before `AUTO_UPLOAD=true` is treated as intentional.
- `AUTO_UPLOAD_MUST_BE_APPROVED`: Requires explicit upload approval. Default `true`.
- `ANALYTICS_DUE_ENABLED`: Enables analytics due workflow.
- `WORKFLOW_LOG_DIR`: Local logs and lock directory.
- `SCHEDULER_LOCK_ENABLED`: Enables local workflow lock files.
- `SCHEDULER_LOCK_TIMEOUT_MINUTES`: Stale lock timeout.

Never commit real values for API keys, OAuth tokens, refresh tokens, or client secrets.

## Gemini-Compatible Example

```env
LLM_PROVIDER=gemini
LLM_API_KEY=replace-with-your-key
LLM_MODEL=replace-with-gemini-compatible-model
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta
```

Use `LLM_PROVIDER=mock` or pass `--mock` for local tests and dry runs.

## Free TTS Example

```env
TTS_PROVIDER=free
TTS_VOICE=female_hindi
TTS_LANGUAGE=hi-IN
TTS_SPEAKING_RATE=normal
TTS_OUTPUT_FORMAT=mp3
TTS_MAX_RETRIES=2
TTS_CACHE_DIR=./outputs/assets/audio
```

## Stock Media Example

```env
STOCK_MEDIA_PROVIDER=pexels
PEXELS_API_KEY=replace-with-free-pexels-key
STOCK_MEDIA_RESULTS_PER_BEAT=3
STOCK_MEDIA_DOWNLOAD_ENABLED=false
```

## Render Example

```env
VIDEO_RENDERER=ffmpeg
FFMPEG_BINARY=ffmpeg
RENDER_OUTPUT_DIR=./outputs/renders
RENDER_WIDTH=1080
RENDER_HEIGHT=1920
RENDER_FPS=30
RENDER_VIDEO_CODEC=libx264
RENDER_AUDIO_CODEC=aac
WATERMARK_ENABLED=true
WATERMARK_TEXT=RaatVerse
SUBTITLE_STYLE=shorts_high_contrast
```

## YouTube Upload Example

```env
YOUTUBE_CLIENT_ID=replace-with-youtube-oauth-client-id
YOUTUBE_CLIENT_SECRET=replace-with-youtube-oauth-client-secret
YOUTUBE_REDIRECT_URI=http://localhost:8080/oauth2callback
YOUTUBE_TOKEN_FILE=./secrets/youtube_token.json
YOUTUBE_SCOPES=https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/yt-analytics.readonly https://www.googleapis.com/auth/youtube.readonly
YOUTUBE_CATEGORY_ID=24
YOUTUBE_DEFAULT_LANGUAGE=hi
YOUTUBE_CONTAINS_SYNTHETIC_MEDIA=true
YOUTUBE_SELF_DECLARED_MADE_FOR_KIDS=false
YOUTUBE_DEFAULT_SCHEDULE_TIME=20:00
UPLOAD_PRIVACY_STATUS=private
```

## YouTube Analytics Example

```env
YOUTUBE_ANALYTICS_ENABLED=true
YOUTUBE_ANALYTICS_BASE_URL=https://youtubeanalytics.googleapis.com/v2
ANALYTICS_DEFAULT_WINDOWS=24h,48h,7d
ANALYTICS_WEIGHT_VIEWS=0.35
ANALYTICS_WEIGHT_LIKE_RATE=0.20
ANALYTICS_WEIGHT_COMMENT_RATE=0.10
ANALYTICS_WEIGHT_RETENTION=0.25
ANALYTICS_WEIGHT_SUBSCRIBERS=0.10
ANALYTICS_EARLY_WINDOW_WEIGHT=0.60
ANALYTICS_SEVEN_DAY_WEIGHT=0.40
STRATEGY_EXPLOITATION_RATE=0.70
STRATEGY_EXPLORATION_RATE=0.30
```

## Operations Example

```env
AUTOMATION_MODE=mock
DAILY_DRAFT_ENABLED=true
DAILY_DRAFT_TIME=20:00
SCHEDULER_TIMEZONE=Asia/Kolkata
DAILY_AUTO_CATEGORY=true
DAILY_STOP_AFTER_DRAFT=true
AUTO_PREPARE_ASSETS=false
AUTO_RENDER=false
AUTO_PREPARE_UPLOAD=false
AUTO_UPLOAD=false
AUTO_UPLOAD_MUST_BE_APPROVED=true
ANALYTICS_DUE_ENABLED=true
WORKFLOW_LOG_DIR=./outputs/logs
SCHEDULER_LOCK_ENABLED=true
SCHEDULER_LOCK_TIMEOUT_MINUTES=60
```

## Dashboard, Persistence, and Notifications

```env
DASHBOARD_ENABLED=true
DASHBOARD_REQUIRE_TOKEN=false
DASHBOARD_PROTECT_READS=false
DASHBOARD_ADMIN_TOKEN=
DASHBOARD_SESSION_COOKIE_ENABLED=false
DASHBOARD_ALLOWED_HOSTS=localhost,127.0.0.1

DB_ENGINE=sqlite
DATABASE_URL=sqlite:///./data/raatverse_agent.db
DB_BACKUP_DIR=./outputs/backups
DB_EXPORT_DIR=./outputs/exports
DB_BACKUP_RETENTION=20
DB_BACKUP_BEFORE_UPGRADE=true
RELEASE_BACKUP_REQUIRED=true
AUDIT_LOG_ENABLED=true
AUDIT_EXPORT_DIR=./outputs/audit_exports

NOTIFICATIONS_ENABLED=false
NOTIFICATION_PROVIDER=mock
NOTIFICATION_WEBHOOK_URL=
NOTIFY_ON_DRAFT_CREATED=true
NOTIFY_ON_WORKFLOW_FAILED=true
NOTIFY_ON_UPLOAD_READY=true
NOTIFY_ON_ANALYTICS_READY=true
```

Enable `DASHBOARD_REQUIRE_TOKEN=true` and set a long random `DASHBOARD_ADMIN_TOKEN` before exposing the dashboard outside localhost.

In production, also consider `DASHBOARD_PROTECT_READS=true`, a reverse proxy auth layer, and regular SQLite backups or optional Postgres.
