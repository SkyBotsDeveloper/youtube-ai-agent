from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

SnapshotWindow = Literal["24h", "48h", "7d", "manual"]
AnalyticsSnapshotStatus = Literal["snapshot_ready", "snapshot_empty", "snapshot_failed"]


class AnalyticsFetchRequest(BaseModel):
    mock: bool = False
    snapshot_window: SnapshotWindow | None = None


class AnalyticsFetchAllRequest(BaseModel):
    mock: bool = False
    snapshot_window: SnapshotWindow | None = None
    only_due: bool = False


class AnalyticsMetricBundle(BaseModel):
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    estimated_minutes_watched: float = 0.0
    average_view_duration: float = 0.0
    subscribers_gained: int = 0
    subscribers_lost: int = 0
    raw_response_json: dict | None = None


class AnalyticsSnapshot(BaseModel):
    id: int | None = None
    youtube_upload_id: int
    youtube_video_id: str
    script_draft_id: int
    category: str
    story_type: str
    snapshot_window: SnapshotWindow = "manual"
    snapshot_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    days_since_upload: float = 0.0
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    estimated_minutes_watched: float = 0.0
    average_view_duration: float = 0.0
    subscribers_gained: int = 0
    subscribers_lost: int = 0
    like_rate: float = 0.0
    comment_rate: float = 0.0
    subscriber_gain_rate: float = 0.0
    retention_score: float = 0.0
    performance_score: float = 0.0
    confidence: float = 0.0
    raw_response_json: dict | None = None
    provider: str = "mock"
    status: AnalyticsSnapshotStatus = "snapshot_ready"
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CategoryScoreSummary(BaseModel):
    id: int | None = None
    category: str
    story_type: str | None = None
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
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DueSnapshotCandidate(BaseModel):
    youtube_upload_id: int
    youtube_video_id: str
    title: str
    status: str
    uploaded_at: datetime
    days_since_upload: float
    due_windows: list[SnapshotWindow] = Field(default_factory=list)


class StrategyCategoryAllocation(BaseModel):
    category: str
    recommended_count: int
    reason: str
    avg_performance_score: float = 0.0
    confidence: float = 0.0


class StrategyRecommendation(BaseModel):
    summary: str
    weekly_distribution: list[StrategyCategoryAllocation] = Field(default_factory=list)
    ranked_categories: list[CategoryScoreSummary] = Field(default_factory=list)
    exploration_rate: float
    exploitation_rate: float
    avoid_notes: list[str] = Field(default_factory=list)
    next_category: str | None = None
    machine_plan: dict = Field(default_factory=dict)
