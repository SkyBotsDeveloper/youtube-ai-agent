from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

RenderStatus = Literal["render_pending", "render_running", "render_ready", "render_failed"]


class RenderRequest(BaseModel):
    mock: bool = False
    force: bool = False
    strict_quality: bool = False


class RenderValidationResult(BaseModel):
    is_valid: bool
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class VideoRender(BaseModel):
    id: int | None = None
    render_uid: str = Field(default_factory=lambda: str(uuid4()))
    asset_plan_id: int
    script_draft_id: int
    status: RenderStatus = "render_pending"
    output_path: str | None = None
    preview_path: str | None = None
    duration_seconds: float | None = None
    resolution: str = "1080x1920"
    fps: int = 30
    renderer_provider: str
    ffmpeg_command_summary: str | None = None
    timing_report: dict = Field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
