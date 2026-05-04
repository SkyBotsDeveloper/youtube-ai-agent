from __future__ import annotations

from datetime import datetime, timezone

from raatverse_agent.analytics.models import AnalyticsFetchRequest
from raatverse_agent.analytics.service import create_analytics_workflow_service
from raatverse_agent.analytics.strategy import StrategyLearningService
from raatverse_agent.assets.models import AssetPreparationRequest
from raatverse_agent.assets.service import create_asset_preparation_service
from raatverse_agent.config import Settings
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.notifications.service import NotificationService
from raatverse_agent.ops.lock import WorkflowLock, WorkflowLockError
from raatverse_agent.ops.models import OpsStatus, ReviewQueue, WorkflowRequest, WorkflowRun, WorkflowRunUpdate
from raatverse_agent.ops.review import ReviewQueueService
from raatverse_agent.rendering.models import RenderRequest
from raatverse_agent.rendering.service import create_render_workflow_service
from raatverse_agent.script_generation.models import ScriptGenerationRequest
from raatverse_agent.script_generation.service import ScriptDraftService, create_script_draft_generator
from raatverse_agent.youtube.models import YouTubeUploadRequest
from raatverse_agent.youtube.service import create_youtube_upload_service


class WorkflowError(RuntimeError):
    pass


class WorkflowOrchestrationService:
    def __init__(self, *, settings: Settings, repository: RaatVerseRepository):
        self.settings = settings
        self.repository = repository

    def run_daily_draft(self, request: WorkflowRequest | None = None) -> WorkflowRun:
        request = request or WorkflowRequest()
        mock = request.mock or self.settings.automation_mode == "mock"
        run = self._start_run("daily_draft", mock=mock, dry_run=request.dry_run)
        try:
            with WorkflowLock(self.settings, "daily-draft"):
                if request.dry_run:
                    return self._finish_run(run, "skipped", {"message": "Dry run; no draft generated."})
                if not self.settings.daily_draft_enabled:
                    return self._finish_run(run, "skipped", {"message": "DAILY_DRAFT_ENABLED=false"})

                generator = create_script_draft_generator(self.settings, mock=mock)
                service = ScriptDraftService(
                    settings=self.settings,
                    repository=self.repository,
                    generator=generator,
                )
                response = service.generate(
                    ScriptGenerationRequest(
                        mock=mock,
                        auto_category=self.settings.daily_auto_category,
                    )
                )
                if response.draft is None:
                    raise WorkflowError(response.error or "Daily draft generation returned no draft.")

                summary = {
                    "message": "Daily draft generated and waiting for human review.",
                    "draft_status": response.draft.status,
                    "title": response.draft.title,
                    "category": response.draft.category,
                    "story_type": response.draft.story_type,
                    "daily_stop_after_draft": self.settings.daily_stop_after_draft,
                    "next_action": "Review the draft, then approve or reject it.",
                }
                notification = self._notify(
                    enabled=self.settings.notify_on_draft_created,
                    event="draft_created",
                    title="RaatVerse draft created",
                    body=f"Draft {response.saved_draft_id}: {response.draft.title}",
                    data={"script_id": response.saved_draft_id, "category": response.draft.category},
                    mock=mock,
                )
                if notification:
                    summary["notification"] = notification
                if not self.settings.daily_stop_after_draft:
                    summary["continuation"] = (
                        "Safe continuation flags are configured, but a new script draft still "
                        "requires human approval before assets/render/upload preparation."
                    )
                return self._finish_run(
                    run,
                    "success",
                    summary,
                    created_script_id=response.saved_draft_id,
                )
        except WorkflowLockError as exc:
            return self._finish_run(run, "skipped", {"message": str(exc)}, error_message=str(exc))
        except Exception as exc:
            self._notify_workflow_failed("daily_draft", str(exc), mock=mock)
            return self._finish_run(run, "failed", {"message": "Daily draft workflow failed."}, error_message=str(exc))

    def run_full_mock(self) -> WorkflowRun:
        run = self._start_run("full_mock", mock=True, dry_run=False)
        try:
            with WorkflowLock(self.settings, "full-mock"):
                generator = create_script_draft_generator(self.settings, mock=True)
                script_service = ScriptDraftService(
                    settings=self.settings,
                    repository=self.repository,
                    generator=generator,
                )
                response = script_service.generate(
                    ScriptGenerationRequest(mock=True, auto_category=True)
                )
                if response.draft is None or response.saved_draft_id is None:
                    raise WorkflowError(response.error or "Full mock did not create a draft.")
                draft = self.repository.update_script_draft_status(response.saved_draft_id, "approved")
                if draft is None:
                    raise WorkflowError("Full mock draft could not be approved.")

                asset_service = create_asset_preparation_service(
                    settings=self.settings,
                    repository=self.repository,
                    mock=True,
                )
                plan = asset_service.prepare_for_script(draft.id, AssetPreparationRequest(mock=True))
                render_service = create_render_workflow_service(
                    settings=self.settings,
                    repository=self.repository,
                    mock=True,
                )
                render = render_service.create_render(plan.id, RenderRequest(mock=True))
                youtube_service = create_youtube_upload_service(
                    settings=self.settings,
                    repository=self.repository,
                    mock=True,
                )
                upload = youtube_service.prepare_upload(render.id)
                upload_notification = self._notify(
                    enabled=self.settings.notify_on_upload_ready,
                    event="upload_ready",
                    title="RaatVerse upload metadata ready",
                    body=f"Upload record {upload.id} is waiting for approval.",
                    data={"upload_id": upload.id, "render_id": render.id},
                    mock=True,
                )
                approved = youtube_service.approve_upload(upload.id)
                uploaded = youtube_service.upload(approved.id, YouTubeUploadRequest(mock=True))
                analytics_service = create_analytics_workflow_service(
                    settings=self.settings,
                    repository=self.repository,
                    mock=True,
                )
                snapshot = analytics_service.fetch_for_upload(
                    uploaded.id,
                    AnalyticsFetchRequest(mock=True),
                )
                scores = StrategyLearningService(
                    settings=self.settings,
                    repository=self.repository,
                ).update_category_scores()
                summary = {
                    "message": "Full mock workflow completed with private mock upload.",
                    "script_title": draft.title,
                    "analytics_snapshot_id": snapshot.id,
                    "category_scores_updated": len(scores),
                    "safety": "Mock upload only; public upload was not used.",
                }
                if upload_notification:
                    summary["upload_ready_notification"] = upload_notification
                return self._finish_run(
                    run,
                    "success",
                    summary,
                    created_script_id=draft.id,
                    created_asset_plan_id=plan.id,
                    created_render_id=render.id,
                    created_upload_id=uploaded.id,
                )
        except WorkflowLockError as exc:
            return self._finish_run(run, "skipped", {"message": str(exc)}, error_message=str(exc))
        except Exception as exc:
            self._notify_workflow_failed("full_mock", str(exc), mock=True)
            return self._finish_run(run, "failed", {"message": "Full mock workflow failed."}, error_message=str(exc))

    def run_analytics_due(self, request: WorkflowRequest | None = None) -> WorkflowRun:
        request = request or WorkflowRequest()
        mock = request.mock or self.settings.automation_mode == "mock"
        run = self._start_run("analytics_sync", mock=mock, dry_run=request.dry_run)
        try:
            with WorkflowLock(self.settings, "analytics-due"):
                if request.dry_run:
                    return self._finish_run(run, "skipped", {"message": "Dry run; no analytics fetched."})
                if not self.settings.analytics_due_enabled:
                    return self._finish_run(run, "skipped", {"message": "ANALYTICS_DUE_ENABLED=false"})

                analytics_service = create_analytics_workflow_service(
                    settings=self.settings,
                    repository=self.repository,
                    mock=mock,
                )
                due = analytics_service.due_snapshots()
                snapshots = []
                for candidate in due:
                    for window in candidate.due_windows:
                        snapshots.append(
                            analytics_service.fetch_for_upload(
                                candidate.youtube_upload_id,
                                AnalyticsFetchRequest(mock=mock, snapshot_window=window),
                            )
                        )
                scores = StrategyLearningService(
                    settings=self.settings,
                    repository=self.repository,
                ).update_category_scores()
                notification = self._notify(
                    enabled=self.settings.notify_on_analytics_ready,
                    event="analytics_ready",
                    title="RaatVerse analytics due workflow completed",
                    body=f"Created {len(snapshots)} analytics snapshot(s).",
                    data={"snapshots_created": len(snapshots), "due_uploads": len(due)},
                    mock=mock,
                )
                summary = {
                        "message": "Analytics due workflow completed.",
                        "due_uploads": len(due),
                        "snapshots_created": len(snapshots),
                        "category_scores_updated": len(scores),
                        "failed_snapshots": len([snapshot for snapshot in snapshots if snapshot.status == "snapshot_failed"]),
                    }
                if notification:
                    summary["notification"] = notification
                return self._finish_run(run, "success", summary)
        except WorkflowLockError as exc:
            return self._finish_run(run, "skipped", {"message": str(exc)}, error_message=str(exc))
        except Exception as exc:
            self._notify_workflow_failed("analytics_sync", str(exc), mock=mock)
            return self._finish_run(run, "failed", {"message": "Analytics due workflow failed."}, error_message=str(exc))

    def review_queue(self) -> ReviewQueue:
        return ReviewQueueService(settings=self.settings, repository=self.repository).queue()

    def status(self) -> OpsStatus:
        queue = self.review_queue()
        latest_runs = self.repository.list_workflow_runs(limit=1)
        recommendation = StrategyLearningService(settings=self.settings, repository=self.repository).recommend()
        return OpsStatus(
            status="ok",
            automation_mode=self.settings.automation_mode,
            daily_stop_after_draft=self.settings.daily_stop_after_draft,
            auto_upload=self.settings.auto_upload,
            auto_upload_must_be_approved=self.settings.auto_upload_must_be_approved,
            scheduler_lock_enabled=self.settings.scheduler_lock_enabled,
            pending_review_count=queue.total_pending,
            latest_workflow_run=latest_runs[0] if latest_runs else None,
            strategy_summary=recommendation.summary,
        )

    def _start_run(self, workflow_type: str, *, mock: bool, dry_run: bool) -> WorkflowRun:
        record = self.repository.create_workflow_run(
            WorkflowRun(
                workflow_type=workflow_type,  # type: ignore[arg-type]
                status="running",
                started_at=datetime.now(timezone.utc),
                provider_mode="mock" if mock else "real",
                dry_run=dry_run,
            )
        )
        saved = self.repository.get_workflow_run(record.id)
        if saved is None:
            raise WorkflowError("Workflow run could not be loaded after creation.")
        return saved

    def _finish_run(
        self,
        run: WorkflowRun,
        status: str,
        summary: dict,
        *,
        error_message: str | None = None,
        created_script_id: int | None = None,
        created_asset_plan_id: int | None = None,
        created_render_id: int | None = None,
        created_upload_id: int | None = None,
    ) -> WorkflowRun:
        if run.id is None:
            raise WorkflowError("Cannot finish an unsaved workflow run.")
        updated = self.repository.update_workflow_run(
            run.id,
            WorkflowRunUpdate(
                status=status,  # type: ignore[arg-type]
                summary=summary,
                error_message=error_message,
                created_script_id=created_script_id,
                created_asset_plan_id=created_asset_plan_id,
                created_render_id=created_render_id,
                created_upload_id=created_upload_id,
                finished_at=datetime.now(timezone.utc),
            ),
        )
        if updated is None:
            raise WorkflowError(f"Workflow run {run.id} could not be updated.")
        return updated

    def _notify(
        self,
        *,
        enabled: bool,
        event: str,
        title: str,
        body: str,
        data: dict,
        mock: bool,
    ) -> dict | None:
        if not enabled:
            return None
        try:
            result = NotificationService(self.settings).maybe_event(
                enabled=enabled,
                event=event,
                title=title,
                body=body,
                data=data,
                mock=mock,
            )
        except Exception as exc:
            return {"sent": False, "error": str(exc)}
        return result.model_dump(mode="json") if result else None

    def _notify_workflow_failed(self, workflow_type: str, error: str, *, mock: bool) -> None:
        self._notify(
            enabled=self.settings.notify_on_workflow_failed,
            event="workflow_failed",
            title=f"RaatVerse workflow failed: {workflow_type}",
            body=error,
            data={"workflow_type": workflow_type},
            mock=mock,
        )
