from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, computed_field

WorkflowType = Literal[
    "daily_draft",
    "asset_prepare",
    "render_prepare",
    "upload_prepare",
    "analytics_sync",
    "full_mock",
]
WorkflowStatus = Literal["pending", "running", "success", "failed", "skipped"]


class WorkflowRun(BaseModel):
    id: int | None = None
    workflow_type: WorkflowType
    status: WorkflowStatus = "pending"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    summary: dict = Field(default_factory=dict)
    error_message: str | None = None
    created_script_id: int | None = None
    created_asset_plan_id: int | None = None
    created_render_id: int | None = None
    created_upload_id: int | None = None
    provider_mode: str = "mock"
    dry_run: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkflowRunUpdate(BaseModel):
    status: WorkflowStatus | None = None
    summary: dict | None = None
    error_message: str | None = None
    created_script_id: int | None = None
    created_asset_plan_id: int | None = None
    created_render_id: int | None = None
    created_upload_id: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class WorkflowRequest(BaseModel):
    mock: bool = False
    dry_run: bool = False


class ReviewQueue(BaseModel):
    scripts_pending_review: list[dict] = Field(default_factory=list)
    rejected_scripts: list[dict] = Field(default_factory=list)
    scripts_approved_needing_assets: list[dict] = Field(default_factory=list)
    assets_ready_needing_render: list[dict] = Field(default_factory=list)
    renders_ready_needing_upload_prepare: list[dict] = Field(default_factory=list)
    uploads_pending_approval: list[dict] = Field(default_factory=list)
    uploads_ready_private: list[dict] = Field(default_factory=list)
    analytics_due: list[dict] = Field(default_factory=list)
    failed_workflows: list[dict] = Field(default_factory=list)

    # Compatibility names from Phase 7.
    pending_script_drafts: list[dict] = Field(default_factory=list)
    approved_scripts_needing_assets: list[dict] = Field(default_factory=list)
    asset_plans_needing_render: list[dict] = Field(default_factory=list)
    renders_needing_upload_metadata: list[dict] = Field(default_factory=list)
    upload_records_needing_approval: list[dict] = Field(default_factory=list)
    analytics_snapshots_due: list[dict] = Field(default_factory=list)

    @computed_field
    @property
    def total_pending(self) -> int:
        return (
            len(self.scripts_pending_review or self.pending_script_drafts)
            + len(self.rejected_scripts)
            + len(self.scripts_approved_needing_assets or self.approved_scripts_needing_assets)
            + len(self.assets_ready_needing_render or self.asset_plans_needing_render)
            + len(self.renders_ready_needing_upload_prepare or self.renders_needing_upload_metadata)
            + len(self.uploads_pending_approval or self.upload_records_needing_approval)
            + len(self.uploads_ready_private)
            + len(self.analytics_due or self.analytics_snapshots_due)
            + len(self.failed_workflows)
        )


class OpsStatus(BaseModel):
    status: str
    automation_mode: str
    daily_stop_after_draft: bool
    auto_upload: bool
    auto_upload_must_be_approved: bool
    scheduler_lock_enabled: bool
    pending_review_count: int
    latest_workflow_run: WorkflowRun | None = None
    strategy_summary: str | None = None
