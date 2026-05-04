from __future__ import annotations

from raatverse_agent.analytics.service import create_analytics_workflow_service
from raatverse_agent.config import Settings
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.ops.models import ReviewQueue


class ReviewQueueService:
    def __init__(self, *, settings: Settings, repository: RaatVerseRepository):
        self.settings = settings
        self.repository = repository

    def queue(self) -> ReviewQueue:
        plans = self.repository.list_asset_plans(limit=500)
        renders = self.repository.list_video_renders(limit=500)
        uploads = self.repository.list_youtube_uploads(limit=500)
        plan_script_ids = {plan.script_draft_id for plan in plans}
        rendered_plan_ids = {render.asset_plan_id for render in renders}
        upload_render_ids = {upload.video_render_id for upload in uploads}

        scripts_pending_review = [
            _script_summary(draft)
            for draft in self.repository.list_script_drafts(limit=200)
            if draft.status in {"draft", "needs_revision"}
        ]
        rejected_scripts = [
            _script_summary(draft)
            for draft in self.repository.list_script_drafts(status="rejected", limit=200)
        ]
        scripts_approved_needing_assets = [
            _script_summary(draft)
            for draft in self.repository.list_script_drafts(status="approved", limit=200)
            if draft.id not in plan_script_ids
        ]
        assets_ready_needing_render = [
            _asset_plan_summary(plan)
            for plan in plans
            if plan.status == "asset_ready" and plan.id not in rendered_plan_ids
        ]
        renders_ready_needing_upload_prepare = [
            _render_summary(render)
            for render in renders
            if render.status == "render_ready" and render.id not in upload_render_ids
        ]
        uploads_pending_approval = [
            _upload_summary(upload)
            for upload in uploads
            if upload.status == "upload_pending"
        ]
        uploads_ready_private = [
            _upload_summary(upload)
            for upload in uploads
            if upload.status in {"upload_approved", "upload_private", "upload_scheduled"}
        ]
        due = create_analytics_workflow_service(
            settings=self.settings,
            repository=self.repository,
            mock=True,
        ).due_snapshots()
        failed_workflows = [
            run.model_dump(mode="json")
            for run in self.repository.list_workflow_runs(status="failed", limit=50)
        ]
        analytics_due = [item.model_dump(mode="json") for item in due]
        return ReviewQueue(
            scripts_pending_review=scripts_pending_review,
            rejected_scripts=rejected_scripts,
            scripts_approved_needing_assets=scripts_approved_needing_assets,
            assets_ready_needing_render=assets_ready_needing_render,
            renders_ready_needing_upload_prepare=renders_ready_needing_upload_prepare,
            uploads_pending_approval=uploads_pending_approval,
            uploads_ready_private=uploads_ready_private,
            analytics_due=analytics_due,
            failed_workflows=failed_workflows,
            pending_script_drafts=scripts_pending_review,
            approved_scripts_needing_assets=scripts_approved_needing_assets,
            asset_plans_needing_render=assets_ready_needing_render,
            renders_needing_upload_metadata=renders_ready_needing_upload_prepare,
            upload_records_needing_approval=uploads_pending_approval,
            analytics_snapshots_due=analytics_due,
        )


def _script_summary(draft) -> dict:
    return {
        "id": draft.id,
        "title": draft.title,
        "category": draft.category,
        "story_type": draft.story_type,
        "status": draft.status,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
    }


def _asset_plan_summary(plan) -> dict:
    return {
        "id": plan.id,
        "script_draft_id": plan.script_draft_id,
        "status": plan.status,
        "provider": plan.provider,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
    }


def _render_summary(render) -> dict:
    return {
        "id": render.id,
        "asset_plan_id": render.asset_plan_id,
        "script_draft_id": render.script_draft_id,
        "status": render.status,
        "output_path": render.output_path,
        "created_at": render.created_at.isoformat() if render.created_at else None,
    }


def _upload_summary(upload) -> dict:
    return {
        "id": upload.id,
        "video_render_id": upload.video_render_id,
        "script_draft_id": upload.script_draft_id,
        "status": upload.status,
        "privacy_status": upload.privacy_status,
        "title": upload.title,
        "created_at": upload.created_at.isoformat() if upload.created_at else None,
    }
