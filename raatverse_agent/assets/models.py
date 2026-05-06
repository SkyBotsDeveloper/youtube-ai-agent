from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

AssetStatus = Literal["asset_pending", "asset_ready", "asset_failed"]


class SubtitleTiming(BaseModel):
    index: int = Field(ge=0)
    start_second: float = Field(ge=0)
    end_second: float = Field(ge=0)
    text: str = Field(min_length=1)


class SceneTimingSuggestion(BaseModel):
    index: int = Field(ge=0)
    start_second: float = Field(ge=0)
    end_second: float = Field(ge=0)
    visual_suggestion: str = Field(min_length=1)
    narration: str = Field(default="")


class AudioAsset(BaseModel):
    id: int | None = None
    asset_uid: str = Field(default_factory=lambda: str(uuid4()))
    script_draft_id: int
    provider: str
    voice: str
    language: str
    file_path: str | None = None
    duration_seconds: float | None = None
    tts_text: str | None = None
    tts_chunks: list[str] = Field(default_factory=list)
    tts_quality_metadata: dict = Field(default_factory=dict)
    subtitle_timings: list[SubtitleTiming] = Field(default_factory=list)
    scene_timings: list[SceneTimingSuggestion] = Field(default_factory=list)
    status: AssetStatus = "asset_pending"
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MediaAssetCandidate(BaseModel):
    provider: str
    query: str
    media_type: str
    source_url: str
    creator_name: str | None = None
    license_note: str | None = None
    local_file_path: str | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    beat_index: int = 0
    score: float = 0.0


class AssetPlan(BaseModel):
    id: int | None = None
    plan_uid: str = Field(default_factory=lambda: str(uuid4()))
    script_draft_id: int
    audio_asset_id: int | None = None
    provider: str
    status: AssetStatus = "asset_pending"
    media_assets: list[MediaAssetCandidate] = Field(default_factory=list)
    subtitle_timings: list[SubtitleTiming] = Field(default_factory=list)
    scene_timings: list[SceneTimingSuggestion] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TTSGenerationRequest(BaseModel):
    mock: bool = False
    force: bool = False


class AssetPreparationRequest(BaseModel):
    mock: bool = False
    force: bool = False
    download_enabled: bool | None = None


class AssetBeatAlignment(BaseModel):
    beat_index: int = Field(ge=0)
    narration_excerpt: str = ""
    selected_media_url: str | None = None
    query_used: str | None = None
    visual_relevance_score: float = 0.0
    duration_allocated: float = 0.0
    is_cta_outro: bool = False
    warnings: list[str] = Field(default_factory=list)


class AssetQualityReport(BaseModel):
    asset_plan_id: int | None = None
    total_beats: int = 0
    total_media_assets: int = 0
    unique_media_urls: int = 0
    repeated_urls: list[str] = Field(default_factory=list)
    vertical_media_count: int = 0
    missing_local_files: int = 0
    provider_distribution: dict[str, int] = Field(default_factory=dict)
    weak_beats: list[int] = Field(default_factory=list)
    unique_media_ratio: float = 0.0
    beat_alignments: list[AssetBeatAlignment] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
