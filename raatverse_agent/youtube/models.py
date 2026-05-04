from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

YouTubeUploadStatus = Literal[
    "upload_pending",
    "upload_approved",
    "upload_running",
    "upload_private",
    "upload_scheduled",
    "upload_failed",
]


class YouTubeMetadata(BaseModel):
    title: str = Field(max_length=100)
    description: str
    tags: list[str] = Field(default_factory=list)
    category_id: str = "24"
    privacy_status: str = "private"
    scheduled_publish_at: datetime | None = None
    contains_synthetic_media: bool = True
    self_declared_made_for_kids: bool = False
    default_language: str = "hi"


class YouTubeUpload(BaseModel):
    id: int | None = None
    video_render_id: int
    script_draft_id: int
    asset_plan_id: int
    status: YouTubeUploadStatus = "upload_pending"
    youtube_video_id: str | None = None
    youtube_url: str | None = None
    privacy_status: str = "private"
    scheduled_publish_at: datetime | None = None
    title: str
    description: str
    tags: list[str] = Field(default_factory=list)
    category_id: str = "24"
    contains_synthetic_media: bool = True
    self_declared_made_for_kids: bool = False
    upload_provider: str = "mock"
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class YouTubeUploadRequest(BaseModel):
    mock: bool = False
    approve_now: bool = False


class YouTubeScheduleRequest(BaseModel):
    publish_at: str | None = None
    schedule_next: bool = False


class YouTubeUploadResult(BaseModel):
    youtube_video_id: str
    youtube_url: str
    status: Literal["upload_private", "upload_scheduled"]


class OAuthTokenStatus(BaseModel):
    has_client_id: bool
    has_client_secret: bool
    has_env_refresh_token: bool
    token_file_path: str
    token_file_exists: bool
    has_file_refresh_token: bool = False
    has_file_access_token: bool = False
    access_token_expires_at: str | None = None
    configured_scopes: list[str] = Field(default_factory=list)
    token_scopes: list[str] = Field(default_factory=list)
    has_analytics_scope: bool = False
