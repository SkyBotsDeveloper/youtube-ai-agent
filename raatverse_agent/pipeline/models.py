from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class CategoryScoreState(BaseModel):
    category: str
    story_type: str | None = None
    score: float = 0.0
    impressions: int = 0
    views: int = 0
    likes: int = 0
    uploads: int = 0
    total_videos: int = 0
    avg_views: float = 0.0
    avg_likes: float = 0.0
    avg_comments: float = 0.0
    avg_like_rate: float = 0.0
    avg_comment_rate: float = 0.0
    avg_average_view_duration: float = 0.0
    avg_subscribers_gained: float = 0.0
    avg_performance_score: float = 0.0
    trend_score: float = 0.0
    confidence: float = 0.0


class StoryIdeaResult(BaseModel):
    idea_uid: str
    category: str
    seed: str
    premise: str
    target_duration_seconds: int
    language: str = "Hindi/Hinglish"


class ScriptResult(BaseModel):
    title: str
    hook: str
    script: str
    category: str
    estimated_duration_seconds: int
    outro_cta: str


class VisualAssetRef(BaseModel):
    provider: str
    query: str
    kind: str = "stock-video"
    duration_seconds: int
    license_note: str


class VoiceoverMetadata(BaseModel):
    provider: str
    voice_name: str
    language_code: str
    estimated_duration_seconds: int
    audio_path: str | None = None
    is_mock: bool = True


class RenderMetadata(BaseModel):
    renderer: str
    output_path: str
    resolution: str = "1080x1920"
    aspect_ratio: str = "9:16"
    duration_seconds: int
    is_mock: bool = True


class ThumbnailMetadata(BaseModel):
    provider: str
    title: str
    image_path: str | None = None
    is_mock: bool = True


class UploadMetadata(BaseModel):
    provider: str
    privacy_status: str
    title: str
    description: str
    tags: list[str] = Field(default_factory=list)
    scheduled_for: str | None = None
    youtube_video_id: str | None = None
    approval_required: bool = True
    is_mock: bool = True


class AnalyticsSnapshotResult(BaseModel):
    provider: str
    video_id: str
    views: int = 0
    likes: int = 0
    comments: int = 0
    average_view_duration_seconds: float = 0.0
    is_mock: bool = True


class PipelineSummary(BaseModel):
    run_uid: str
    mode: str = "mock"
    status: str
    category: str
    title: str
    script_excerpt: str
    visual_assets: list[VisualAssetRef]
    voiceover: VoiceoverMetadata
    render: RenderMetadata
    thumbnail: ThumbnailMetadata
    upload: UploadMetadata
    next_action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
