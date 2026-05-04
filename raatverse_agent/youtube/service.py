from __future__ import annotations

from pathlib import Path

from raatverse_agent.config import Settings
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.youtube.metadata import (
    generate_youtube_metadata,
    next_default_publish_time,
    parse_publish_at,
)
from raatverse_agent.youtube.models import (
    YouTubeMetadata,
    YouTubeScheduleRequest,
    YouTubeUpload,
    YouTubeUploadRequest,
)
from raatverse_agent.youtube.uploader import YouTubeUploadError, create_youtube_uploader


class YouTubeWorkflowError(RuntimeError):
    pass


class YouTubeUploadWorkflowService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: RaatVerseRepository,
        uploader,
    ):
        self.settings = settings
        self.repository = repository
        self.uploader = uploader

    def metadata_preview(self, render_id: int) -> YouTubeMetadata:
        draft, asset_plan, render = self._load_render_context(render_id)
        return generate_youtube_metadata(
            settings=self.settings,
            draft=draft,
            render=render,
            asset_plan=asset_plan,
        )

    def prepare_upload(self, render_id: int) -> YouTubeUpload:
        draft, asset_plan, render = self._load_render_context(render_id)
        self._validate_render_for_upload(render)
        metadata = generate_youtube_metadata(
            settings=self.settings,
            draft=draft,
            render=render,
            asset_plan=asset_plan,
        )
        upload = YouTubeUpload(
            video_render_id=render.id or render_id,
            script_draft_id=draft.id or render.script_draft_id,
            asset_plan_id=asset_plan.id or render.asset_plan_id,
            status="upload_pending",
            privacy_status="private",
            scheduled_publish_at=metadata.scheduled_publish_at,
            title=metadata.title,
            description=metadata.description,
            tags=metadata.tags,
            category_id=metadata.category_id,
            contains_synthetic_media=metadata.contains_synthetic_media,
            self_declared_made_for_kids=metadata.self_declared_made_for_kids,
            upload_provider="mock" if self.uploader.__class__.__name__.startswith("Mock") else "youtube-data-api",
        )
        record = self.repository.create_youtube_upload(upload)
        saved = self.repository.get_youtube_upload(record.id)
        if saved is None:
            raise YouTubeWorkflowError("Saved YouTube upload record could not be loaded.")
        return saved

    def approve_upload(self, upload_id: int) -> YouTubeUpload:
        upload = self.repository.approve_youtube_upload(upload_id)
        if upload is None:
            raise YouTubeWorkflowError(f"YouTube upload {upload_id} was not found.")
        return upload

    def schedule_upload(self, upload_id: int, request: YouTubeScheduleRequest) -> YouTubeUpload:
        upload = self.repository.get_youtube_upload(upload_id)
        if upload is None:
            raise YouTubeWorkflowError(f"YouTube upload {upload_id} was not found.")
        if request.schedule_next:
            publish_at = next_default_publish_time(self.settings)
        elif request.publish_at:
            publish_at = parse_publish_at(request.publish_at)
        else:
            raise YouTubeWorkflowError("Provide --publish-at or --schedule-next.")
        scheduled = self.repository.update_youtube_upload_schedule(upload_id, publish_at)
        if scheduled is None:
            raise YouTubeWorkflowError(f"YouTube upload {upload_id} was not found.")
        return scheduled

    def upload(self, upload_id: int, request: YouTubeUploadRequest) -> YouTubeUpload:
        upload = self.repository.get_youtube_upload(upload_id)
        if upload is None:
            raise YouTubeWorkflowError(f"YouTube upload {upload_id} was not found.")
        if upload.status != "upload_approved":
            if request.mock and request.approve_now:
                upload = self.approve_upload(upload_id)
            else:
                raise YouTubeWorkflowError(
                    "Upload must be explicitly approved before upload. Run youtube approve-upload first."
                )

        render = self.repository.get_video_render(upload.video_render_id)
        if render is None:
            raise YouTubeWorkflowError(f"Render {upload.video_render_id} was not found.")
        self._validate_render_for_upload(render)

        running = self.repository.update_youtube_upload_status(upload_id, "upload_running")
        if running is None:
            raise YouTubeWorkflowError(f"YouTube upload {upload_id} was not found.")

        try:
            result = self.uploader.upload(upload, render)
        except YouTubeUploadError as exc:
            failed = self.repository.update_youtube_upload_status(
                upload_id,
                "upload_failed",
                error_message=str(exc),
            )
            if failed is None:
                raise YouTubeWorkflowError("Failed upload record could not be loaded.") from exc
            return failed

        completed = self.repository.update_youtube_upload_status(
            upload_id,
            result.status,
            youtube_video_id=result.youtube_video_id,
            youtube_url=result.youtube_url,
        )
        if completed is None:
            raise YouTubeWorkflowError("Completed upload record could not be loaded.")
        return completed

    def _load_render_context(self, render_id: int):
        render = self.repository.get_video_render(render_id)
        if render is None:
            raise YouTubeWorkflowError(f"Video render {render_id} was not found.")
        draft = self.repository.get_script_draft(render.script_draft_id)
        if draft is None:
            raise YouTubeWorkflowError(f"Script draft {render.script_draft_id} was not found.")
        asset_plan = self.repository.get_asset_plan(render.asset_plan_id)
        if asset_plan is None:
            raise YouTubeWorkflowError(f"Asset plan {render.asset_plan_id} was not found.")
        return draft, asset_plan, render

    def _validate_render_for_upload(self, render) -> None:
        if render.status != "render_ready":
            raise YouTubeWorkflowError("Render must be render_ready before upload preparation.")
        output_path = Path(render.output_path or "")
        if not output_path.exists():
            raise YouTubeWorkflowError(f"Render output file does not exist: {output_path}")


def create_youtube_upload_service(
    *,
    settings: Settings,
    repository: RaatVerseRepository,
    mock: bool = False,
) -> YouTubeUploadWorkflowService:
    return YouTubeUploadWorkflowService(
        settings=settings,
        repository=repository,
        uploader=create_youtube_uploader(settings, mock=mock),
    )
