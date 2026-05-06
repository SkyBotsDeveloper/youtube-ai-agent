from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from raatverse_agent import __version__


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_version: str = __version__
    app_env: str = "local"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./data/raatverse_agent.db"

    channel_name: str = "RaatVerse"
    youtube_channel_handle: str = "@RaatVerseHindi"
    default_timezone: str = "Asia/Kolkata"
    daily_upload_time: str = "21:00"
    human_approval_required: bool = True
    upload_privacy_status: Literal["private", "unlisted", "public"] = "private"
    story_categories_csv: str = (
        "horror,mystery,suspense,emotional_twist,thriller,urban_legend,psychological"
    )
    script_categories_csv: str = (
        "horror,mystery,suspense,emotional_twist,thriller,urban_legend,psychological"
    )
    language_style: str = "Hinglish with natural Hindi storytelling"
    min_video_seconds: int = Field(default=35, ge=1)
    max_video_seconds: int = Field(default=75, ge=1)
    script_min_words: int = Field(default=80, ge=1)
    script_max_words: int = Field(default=230, ge=1)
    script_similarity_threshold: float = Field(default=0.82, ge=0.0, le=1.0)
    script_recent_window: int = Field(default=8, ge=1)
    script_max_recent_same_category_story_type: int = Field(default=2, ge=1)
    script_exploitation_rate: float = Field(default=0.70, ge=0.0, le=1.0)
    script_generation_max_attempts: int = Field(default=2, ge=1)
    outro_cta: str = (
        "Agar kahani pasand aayi ho, to RaatVerse ko subscribe karo. "
        "Kal raat ek aur nayi kahani milegi."
    )

    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_model: str = "gemini-compatible-model"
    llm_base_url: str = ""
    llm_timeout_seconds: float = Field(default=30.0, ge=1.0)
    llm_temperature: float = Field(default=0.85, ge=0.0, le=2.0)

    tts_provider: str = "mock"
    tts_api_key: str = ""
    tts_voice_id: str = "raatverse-hindi-narrator"
    tts_voice: str = "hi-IN-SwaraNeural"
    tts_language: str = "hi-IN"
    tts_speaking_rate: str = "normal"
    tts_output_format: str = "mp3"
    tts_max_retries: int = Field(default=2, ge=0)
    tts_cache_dir: str = "./outputs/assets/audio"
    tts_text_mode: Literal["auto", "raw", "devanagari"] = "auto"
    tts_use_devanagari: bool = True
    tts_max_chars_per_chunk: int = Field(default=450, ge=80)
    tts_pause_style: Literal["punctuation", "plain"] = "punctuation"

    stock_media_provider: str = "mock"
    pexels_api_key: str = ""
    pixabay_api_key: str = ""
    stock_media_results_per_beat: int = Field(default=3, ge=1, le=20)
    stock_media_cache_dir: str = "./outputs/assets/media"
    stock_media_download_enabled: bool = False
    stock_media_timeout_seconds: float = Field(default=20.0, ge=1.0)
    stock_media_avoid_duplicates: bool = True
    stock_media_min_unique_per_plan: int = Field(default=6, ge=1)
    stock_media_prefer_vertical: bool = True
    stock_media_max_reuse_per_url: int = Field(default=1, ge=1)
    visual_relevance_min_score: float = Field(default=0.55, ge=0.0, le=1.0)
    visual_relevance_prefer_location: bool = True
    visual_relevance_prefer_action: bool = True
    visual_relevance_prefer_mood: bool = True

    ffmpeg_binary: str = "ffmpeg"
    output_dir: str = "./outputs"
    video_renderer: str = "mock"
    render_output_dir: str = "./outputs/renders"
    render_width: int = Field(default=1080, ge=1)
    render_height: int = Field(default=1920, ge=1)
    render_fps: int = Field(default=30, ge=1)
    render_video_codec: str = "libx264"
    render_audio_codec: str = "aac"
    render_preset: str = "veryfast"
    render_crf: int = Field(default=23, ge=0, le=51)
    render_mock_enabled: bool = True
    watermark_enabled: bool = True
    watermark_text: str = "RaatVerse"
    watermark_position: str = "top-right"
    subtitle_style: str = "shorts_high_contrast"
    cta_min_duration_seconds: float = Field(default=7.0, ge=1.0)
    cta_end_padding_seconds: float = Field(default=1.5, ge=0.0)
    cta_visual_hold_seconds: float = Field(default=2.0, ge=0.0)
    min_scene_beat_duration_seconds: float = Field(default=2.5, ge=0.5)
    min_subtitle_duration_seconds: float = Field(default=1.2, ge=0.5)

    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    youtube_redirect_uri: str = "http://localhost:8080/oauth2callback"
    youtube_refresh_token: str = ""
    youtube_token_file: str = "./secrets/youtube_token.json"
    youtube_token_uri: str = "https://oauth2.googleapis.com/token"
    youtube_scopes: str = (
        "https://www.googleapis.com/auth/youtube.upload "
        "https://www.googleapis.com/auth/yt-analytics.readonly "
        "https://www.googleapis.com/auth/youtube.readonly"
    )
    youtube_category_id: str = "24"
    youtube_default_language: str = "hi"
    youtube_contains_synthetic_media: bool = True
    youtube_self_declared_made_for_kids: bool = False
    youtube_default_schedule_time: str = "20:00"
    analytics_fetch_enabled: bool = False
    youtube_analytics_enabled: bool = False
    youtube_analytics_base_url: str = "https://youtubeanalytics.googleapis.com/v2"
    analytics_default_windows: str = "24h,48h,7d"
    analytics_weight_views: float = Field(default=0.35, ge=0.0)
    analytics_weight_like_rate: float = Field(default=0.20, ge=0.0)
    analytics_weight_comment_rate: float = Field(default=0.10, ge=0.0)
    analytics_weight_retention: float = Field(default=0.25, ge=0.0)
    analytics_weight_subscribers: float = Field(default=0.10, ge=0.0)
    analytics_early_window_weight: float = Field(default=0.60, ge=0.0, le=1.0)
    analytics_seven_day_weight: float = Field(default=0.40, ge=0.0, le=1.0)
    strategy_exploitation_rate: float = Field(default=0.70, ge=0.0, le=1.0)
    strategy_exploration_rate: float = Field(default=0.30, ge=0.0, le=1.0)

    automation_mode: Literal["mock", "real"] = "mock"
    daily_draft_enabled: bool = True
    daily_draft_time: str = "20:00"
    scheduler_timezone: str = "Asia/Kolkata"
    daily_auto_category: bool = True
    daily_stop_after_draft: bool = True
    auto_prepare_assets: bool = False
    auto_render: bool = False
    auto_prepare_upload: bool = False
    auto_upload: bool = False
    auto_upload_must_be_approved: bool = True
    analytics_due_enabled: bool = True
    workflow_log_dir: str = "./outputs/logs"
    scheduler_lock_enabled: bool = True
    scheduler_lock_timeout_minutes: int = Field(default=60, ge=1)

    dashboard_enabled: bool = True
    dashboard_require_token: bool = False
    dashboard_admin_token: str = ""
    dashboard_protect_reads: bool = False
    dashboard_session_cookie_enabled: bool = False
    dashboard_allowed_hosts: str = "localhost,127.0.0.1"

    db_engine: Literal["sqlite", "postgres"] = "sqlite"
    db_backup_dir: str = "./outputs/backups"
    db_export_dir: str = "./outputs/exports"
    db_backup_retention: int = Field(default=20, ge=1)
    db_backup_before_upgrade: bool = True
    release_backup_required: bool = True

    notifications_enabled: bool = False
    notification_provider: Literal["mock", "webhook"] = "mock"
    notification_webhook_url: str = ""
    notify_on_draft_created: bool = True
    notify_on_workflow_failed: bool = True
    notify_on_upload_ready: bool = True
    notify_on_analytics_ready: bool = True

    confirm_enable_auto_upload: bool = False
    audit_log_enabled: bool = True
    audit_export_dir: str = "./outputs/audit_exports"

    @property
    def story_categories(self) -> tuple[str, ...]:
        return tuple(
            category.strip()
            for category in self.story_categories_csv.split(",")
            if category.strip()
        )

    @property
    def script_categories(self) -> tuple[str, ...]:
        return tuple(
            category.strip()
            for category in self.script_categories_csv.split(",")
            if category.strip()
        )

    @property
    def all_categories(self) -> tuple[str, ...]:
        categories: list[str] = []
        for category in (*self.story_categories, *self.script_categories):
            if category not in categories:
                categories.append(category)
        return tuple(categories)

    @property
    def target_duration_seconds(self) -> int:
        return round((self.min_video_seconds + self.max_video_seconds) / 2)

    @property
    def youtube_scope_list(self) -> tuple[str, ...]:
        return tuple(scope for scope in self.youtube_scopes.split() if scope)

    @property
    def analytics_windows(self) -> tuple[str, ...]:
        return tuple(
            window.strip()
            for window in self.analytics_default_windows.split(",")
            if window.strip()
        )

    @property
    def dashboard_allowed_host_list(self) -> tuple[str, ...]:
        return tuple(
            host.strip().lower()
            for host in self.dashboard_allowed_hosts.split(",")
            if host.strip()
        )

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def safety_warnings(self) -> tuple[str, ...]:
        warnings: list[str] = []
        if self.auto_upload and not self.confirm_enable_auto_upload:
            warnings.append(
                "AUTO_UPLOAD=true is ignored as unsafe unless CONFIRM_ENABLE_AUTO_UPLOAD=true is set."
            )
        if self.dashboard_require_token and not self.dashboard_admin_token:
            warnings.append("DASHBOARD_REQUIRE_TOKEN=true but DASHBOARD_ADMIN_TOKEN is empty.")
        if self.db_engine == "postgres" and not self.database_url.startswith(("postgres://", "postgresql://")):
            warnings.append("DB_ENGINE=postgres requires a postgres/postgresql DATABASE_URL.")
        if self.is_production and self.database_url.startswith("sqlite"):
            warnings.append("Production mode is using SQLite; configure regular backups or optional Postgres.")
        if self.is_production and not self.dashboard_require_token:
            warnings.append("Production mode should set DASHBOARD_REQUIRE_TOKEN=true.")
        if self.is_production and not self.dashboard_protect_reads:
            warnings.append("Production mode should set DASHBOARD_PROTECT_READS=true.")
        if self.is_production and not self.db_backup_before_upgrade:
            warnings.append("Production mode should keep DB_BACKUP_BEFORE_UPGRADE=true.")
        if self.is_production and not self.release_backup_required:
            warnings.append("Production mode should keep RELEASE_BACKUP_REQUIRED=true.")
        if self.auto_upload:
            warnings.append("AUTO_UPLOAD should stay false for the human-approved RaatVerse workflow.")
        return tuple(warnings)

    @property
    def effective_auto_upload(self) -> bool:
        return self.auto_upload and self.confirm_enable_auto_upload


@lru_cache
def get_settings() -> Settings:
    return Settings()
