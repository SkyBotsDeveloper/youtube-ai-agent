from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(80), index=True)
    script_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    youtube_video_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    privacy_status: Mapped[str] = mapped_column(String(20), default="private")
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    analytics_snapshots: Mapped[list["AnalyticsSnapshot"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )


class StoryIdea(Base):
    __tablename__ = "story_ideas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idea_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    seed: Mapped[str] = mapped_column(String(255))
    premise: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="new", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ScriptDraftRecord(Base):
    __tablename__ = "script_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    draft_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(160), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    story_type: Mapped[str] = mapped_column(String(80), index=True)
    hook: Mapped[str] = mapped_column(String(300))
    narration_script: Mapped[str] = mapped_column(Text)
    scene_beats_json: Mapped[list] = mapped_column(JSON, default=list)
    subtitle_lines_json: Mapped[list] = mapped_column(JSON, default=list)
    cta_line: Mapped[str] = mapped_column(Text)
    estimated_duration_seconds: Mapped[int] = mapped_column(Integer)
    language_style: Mapped[str] = mapped_column(String(120))
    safety_notes_json: Mapped[list] = mapped_column(JSON, default=list)
    originality_notes_json: Mapped[list] = mapped_column(JSON, default=list)
    validation_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    provider: Mapped[str] = mapped_column(String(80), default="mock", index=True)
    prompt_version: Mapped[str] = mapped_column(String(80), default="raatverse-script-v1")
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class AudioAssetRecord(Base):
    __tablename__ = "audio_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    script_draft_id: Mapped[int] = mapped_column(ForeignKey("script_drafts.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    voice: Mapped[str] = mapped_column(String(120))
    language: Mapped[str] = mapped_column(String(40))
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    subtitle_timings_json: Mapped[list] = mapped_column(JSON, default=list)
    scene_timings_json: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(40), default="asset_pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AssetPlanRecord(Base):
    __tablename__ = "asset_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    script_draft_id: Mapped[int] = mapped_column(ForeignKey("script_drafts.id"), index=True)
    audio_asset_id: Mapped[int | None] = mapped_column(ForeignKey("audio_assets.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), default="asset_pending", index=True)
    media_assets_json: Mapped[list] = mapped_column(JSON, default=list)
    subtitle_timings_json: Mapped[list] = mapped_column(JSON, default=list)
    scene_timings_json: Mapped[list] = mapped_column(JSON, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class VideoRenderRecord(Base):
    __tablename__ = "video_renders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    render_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    asset_plan_id: Mapped[int] = mapped_column(ForeignKey("asset_plans.id"), index=True)
    script_draft_id: Mapped[int] = mapped_column(ForeignKey("script_drafts.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="render_pending", index=True)
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    preview_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolution: Mapped[str] = mapped_column(String(40), default="1080x1920")
    fps: Mapped[int] = mapped_column(Integer, default=30)
    renderer_provider: Mapped[str] = mapped_column(String(80), index=True)
    ffmpeg_command_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class YouTubeUploadRecord(Base):
    __tablename__ = "youtube_uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_render_id: Mapped[int] = mapped_column(ForeignKey("video_renders.id"), index=True)
    script_draft_id: Mapped[int] = mapped_column(ForeignKey("script_drafts.id"), index=True)
    asset_plan_id: Mapped[int] = mapped_column(ForeignKey("asset_plans.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="upload_pending", index=True)
    youtube_video_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    youtube_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    privacy_status: Mapped[str] = mapped_column(String(20), default="private")
    scheduled_publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    tags_json: Mapped[list] = mapped_column(JSON, default=list)
    category_id: Mapped[str] = mapped_column(String(20), default="24")
    contains_synthetic_media: Mapped[bool] = mapped_column(Boolean, default=True)
    self_declared_made_for_kids: Mapped[bool] = mapped_column(Boolean, default=False)
    upload_provider: Mapped[str] = mapped_column(String(80), default="mock", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Kept nullable for compatibility with the Phase 1 placeholder video table.
    video_id: Mapped[int | None] = mapped_column(ForeignKey("videos.id"), nullable=True, index=True)
    youtube_upload_id: Mapped[int | None] = mapped_column(
        ForeignKey("youtube_uploads.id"), nullable=True, index=True
    )
    youtube_video_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    script_draft_id: Mapped[int | None] = mapped_column(
        ForeignKey("script_drafts.id"), nullable=True, index=True
    )
    category: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    story_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    snapshot_window: Mapped[str] = mapped_column(String(20), default="manual", index=True)
    snapshot_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    days_since_upload: Mapped[float] = mapped_column(Float, default=0.0)
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    estimated_minutes_watched: Mapped[float] = mapped_column(Float, default=0.0)
    average_view_duration: Mapped[float] = mapped_column(Float, default=0.0)
    average_view_duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    subscribers_gained: Mapped[int] = mapped_column(Integer, default=0)
    subscribers_lost: Mapped[int] = mapped_column(Integer, default=0)
    like_rate: Mapped[float] = mapped_column(Float, default=0.0)
    comment_rate: Mapped[float] = mapped_column(Float, default=0.0)
    subscriber_gain_rate: Mapped[float] = mapped_column(Float, default=0.0)
    retention_score: Mapped[float] = mapped_column(Float, default=0.0)
    performance_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    raw_response_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    provider: Mapped[str] = mapped_column(String(80), default="mock", index=True)
    status: Mapped[str] = mapped_column(String(40), default="snapshot_ready", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    video: Mapped[Video | None] = relationship(back_populates="analytics_snapshots")


class CategoryScore(Base):
    __tablename__ = "category_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    story_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    uploads: Mapped[int] = mapped_column(Integer, default=0)
    total_videos: Mapped[int] = mapped_column(Integer, default=0)
    avg_views: Mapped[float] = mapped_column(Float, default=0.0)
    avg_likes: Mapped[float] = mapped_column(Float, default=0.0)
    avg_comments: Mapped[float] = mapped_column(Float, default=0.0)
    avg_like_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_comment_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_average_view_duration: Mapped[float] = mapped_column(Float, default=0.0)
    avg_subscribers_gained: Mapped[float] = mapped_column(Float, default=0.0)
    avg_performance_score: Mapped[float] = mapped_column(Float, default=0.0)
    trend_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    mode: Mapped[str] = mapped_column(String(40), default="mock", index=True)
    status: Mapped[str] = mapped_column(String(40), default="started", index=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkflowRunRecord(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_type: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_script_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_asset_plan_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_render_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_upload_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    provider_mode: Mapped[str] = mapped_column(String(40), default="mock", index=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class AuditLogRecord(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(120), default="system", index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    before_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    after_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(80), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class ApprovalEventRecord(Base):
    __tablename__ = "approval_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(120), default="system", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
