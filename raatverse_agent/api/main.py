from __future__ import annotations

import csv
import io
from collections.abc import Generator
from contextlib import asynccontextmanager
from html import escape
from urllib.parse import parse_qs

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from raatverse_agent.audit.exporting import audit_logs_payload, filtered_audit_logs
from raatverse_agent.analytics.models import AnalyticsFetchAllRequest, AnalyticsFetchRequest
from raatverse_agent.analytics.service import AnalyticsWorkflowError, create_analytics_workflow_service
from raatverse_agent.analytics.strategy import StrategyLearningService
from raatverse_agent.assets.errors import AssetWorkflowError
from raatverse_agent.assets.models import AssetPreparationRequest, TTSGenerationRequest
from raatverse_agent.assets.service import (
    create_asset_preparation_service,
    create_tts_asset_service,
)
from raatverse_agent.config import Settings, get_settings
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.db.session import initialize_database, session_scope
from raatverse_agent.ops.models import WorkflowRequest
from raatverse_agent.ops.health import ops_health_payload
from raatverse_agent.ops.workflow import WorkflowOrchestrationService
from raatverse_agent.pipeline.runner import PipelineRunner
from raatverse_agent.rendering.errors import RenderWorkflowError
from raatverse_agent.rendering.models import RenderRequest
from raatverse_agent.rendering.service import create_render_workflow_service
from raatverse_agent.script_generation.models import ScriptGenerationRequest
from raatverse_agent.script_generation.service import ScriptDraftService, create_script_draft_generator
from raatverse_agent.services.gemini import LLMConfigurationError, LLMProviderError
from raatverse_agent.youtube.models import YouTubeScheduleRequest, YouTubeUploadRequest
from raatverse_agent.youtube.oauth import YouTubeOAuthError, build_oauth_url, token_status
from raatverse_agent.youtube.service import YouTubeWorkflowError, create_youtube_upload_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    initialize_database(settings.database_url)
    with session_scope(settings.database_url) as session:
        RaatVerseRepository(session).init_category_scores(settings.all_categories)
    yield


app = FastAPI(
    title="RaatVerse AI YouTube Shorts Agent",
    version="0.1.0",
    description="Local-first automation API for RaatVerse Shorts generation, rendering, upload, and analytics.",
    lifespan=lifespan,
)


class ScriptRejectRequest(BaseModel):
    reason: str = Field(min_length=1)


class ScriptReviseRequest(BaseModel):
    reason: str = Field(default="Needs revision before approval.", min_length=1)


def get_repository() -> Generator[RaatVerseRepository, None, None]:
    settings = get_settings()
    with session_scope(settings.database_url) as session:
        yield RaatVerseRepository(session)


async def _form_values(request: Request) -> dict[str, str]:
    raw = (await request.body()).decode("utf-8")
    parsed = parse_qs(raw, keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def _check_dashboard_enabled(settings: Settings) -> None:
    if not settings.dashboard_enabled:
        raise HTTPException(status_code=404, detail="Dashboard is disabled.")


def _check_dashboard_token(
    settings: Settings,
    *,
    request: Request | None = None,
    repository: RaatVerseRepository | None = None,
    token: str | None = None,
    header_token: str | None = None,
    form_token: str | None = None,
    read: bool = False,
    action: str = "dashboard_access",
    entity_type: str = "dashboard",
    entity_id: int | None = None,
) -> None:
    _check_dashboard_enabled(settings)
    _check_dashboard_host(settings, request)
    token_required = settings.dashboard_require_token or (read and settings.dashboard_protect_reads)
    if not token_required:
        return
    expected = settings.dashboard_admin_token
    if not expected:
        _audit_dashboard_attempt(
            settings,
            repository,
            request,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            reason="dashboard token required but not configured",
        )
        raise HTTPException(status_code=403, detail="Dashboard token is required but not configured.")
    supplied = token or header_token or form_token
    if supplied != expected:
        _audit_dashboard_attempt(
            settings,
            repository,
            request,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            reason="invalid dashboard token",
        )
        raise HTTPException(status_code=403, detail="Invalid dashboard token.")


def _check_dashboard_host(settings: Settings, request: Request | None) -> None:
    if request is None or not settings.is_production:
        return
    host = (request.headers.get("host") or "").split(":")[0].lower()
    allowed = set(settings.dashboard_allowed_host_list)
    if host and allowed and host not in allowed:
        raise HTTPException(status_code=400, detail="Dashboard host is not allowed.")


def _request_actor(request: Request | None) -> str:
    if request is None:
        return "dashboard"
    host = request.client.host if request.client else "unknown"
    return f"dashboard:{host}"


def _audit_dashboard_attempt(
    settings: Settings,
    repository: RaatVerseRepository | None,
    request: Request | None,
    *,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    before_status: str | None = None,
    after_status: str | None = None,
    reason: str | None = None,
    metadata: dict | None = None,
) -> None:
    if not settings.audit_log_enabled or repository is None:
        return
    repository.create_audit_log(
        actor=_request_actor(request),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_status=before_status,
        after_status=after_status,
        reason=reason,
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
        metadata=metadata,
    )


def _record_approval_event(
    settings: Settings,
    repository: RaatVerseRepository,
    request: Request | None,
    *,
    entity_type: str,
    entity_id: int | None,
    action: str,
    comment: str | None = None,
) -> None:
    if entity_id is None:
        return
    repository.create_approval_event(
        actor=_request_actor(request),
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        comment=comment,
    )


def _dashboard_url(settings: Settings, token: str | None = None, path: str = "/dashboard") -> str:
    if settings.dashboard_require_token or settings.dashboard_protect_reads:
        resolved = token or settings.dashboard_admin_token
        if resolved:
            separator = "&" if "?" in path else "?"
            return f"{path}{separator}token={resolved}"
    return path


def _redirect_dashboard(settings: Settings, token: str | None = None, path: str = "/dashboard") -> RedirectResponse:
    return RedirectResponse(_dashboard_url(settings, token, path), status_code=303)


@app.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "channel": settings.channel_name,
        "handle": settings.youtube_channel_handle,
    }


@app.get("/pipeline/runs")
def pipeline_runs(repository: RaatVerseRepository = Depends(get_repository)) -> dict:
    return {"runs": repository.list_pipeline_runs()}


@app.post("/pipeline/run-mock")
def run_mock_pipeline(
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    summary = PipelineRunner.mock(settings, repository).run_mock()
    return summary.model_dump(mode="json")


@app.post("/scripts/generate")
def generate_script(
    request: ScriptGenerationRequest,
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    try:
        generator = create_script_draft_generator(settings, mock=request.mock)
        service = ScriptDraftService(
            settings=settings,
            repository=repository,
            generator=generator,
        )
        response = service.generate(request)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if response.draft is None:
        raise HTTPException(status_code=422, detail=response.error or response.validation.issues)
    return response.model_dump(mode="json")


@app.get("/scripts")
def list_scripts(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    drafts = repository.list_script_drafts(status=status, limit=limit)
    return {"scripts": [draft.model_dump(mode="json") for draft in drafts]}


@app.get("/scripts/{draft_id}")
def get_script(
    draft_id: int,
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    draft = repository.get_script_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Script draft not found.")
    return draft.model_dump(mode="json")


@app.post("/scripts/{draft_id}/approve")
def approve_script(
    draft_id: int,
    request: Request,
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    before = repository.get_script_draft(draft_id)
    draft = repository.update_script_draft_status(draft_id, "approved")
    if draft is None:
        raise HTTPException(status_code=404, detail="Script draft not found.")
    _audit_dashboard_attempt(
        settings,
        repository,
        request,
        action="script_approve",
        entity_type="script_draft",
        entity_id=draft_id,
        before_status=before.status if before else None,
        after_status=draft.status,
    )
    return draft.model_dump(mode="json")


@app.post("/scripts/{draft_id}/reject")
def reject_script(
    draft_id: int,
    request_context: Request,
    request: ScriptRejectRequest,
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    before = repository.get_script_draft(draft_id)
    draft = repository.update_script_draft_status(draft_id, "rejected", request.reason)
    if draft is None:
        raise HTTPException(status_code=404, detail="Script draft not found.")
    _audit_dashboard_attempt(
        settings,
        repository,
        request_context,
        action="script_reject",
        entity_type="script_draft",
        entity_id=draft_id,
        before_status=before.status if before else None,
        after_status=draft.status,
        reason=request.reason,
    )
    return draft.model_dump(mode="json")


@app.post("/scripts/{draft_id}/revise")
def mark_script_needs_revision(
    draft_id: int,
    request: ScriptReviseRequest,
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    draft = repository.update_script_draft_status(draft_id, "needs_revision", request.reason)
    if draft is None:
        raise HTTPException(status_code=404, detail="Script draft not found.")
    return draft.model_dump(mode="json")


@app.post("/scripts/{draft_id}/regenerate")
def regenerate_script(
    draft_id: int,
    request: ScriptGenerationRequest = Body(default_factory=ScriptGenerationRequest),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    try:
        generator = create_script_draft_generator(settings, mock=request.mock)
        service = ScriptDraftService(
            settings=settings,
            repository=repository,
            generator=generator,
        )
        response = service.regenerate_rejected(draft_id)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if response.draft is None:
        raise HTTPException(status_code=400, detail=response.error or response.validation.issues)
    return response.model_dump(mode="json")


@app.post("/tts/generate/{script_id}")
def generate_tts(
    script_id: int,
    request: TTSGenerationRequest = Body(default_factory=TTSGenerationRequest),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    try:
        service = create_tts_asset_service(
            settings=settings,
            repository=repository,
            mock=request.mock,
        )
        audio = service.generate_for_script(script_id, request)
    except AssetWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return audio.model_dump(mode="json")


@app.post("/assets/prepare/{script_id}")
def prepare_assets(
    script_id: int,
    request: AssetPreparationRequest = Body(default_factory=AssetPreparationRequest),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    try:
        service = create_asset_preparation_service(
            settings=settings,
            repository=repository,
            mock=request.mock,
        )
        plan = service.prepare_for_script(script_id, request)
    except AssetWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return plan.model_dump(mode="json")


@app.get("/assets")
def list_assets(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    plans = repository.list_asset_plans(status=status, limit=limit)
    return {"asset_plans": [plan.model_dump(mode="json") for plan in plans]}


@app.get("/assets/{asset_plan_id}")
def get_asset_plan(
    asset_plan_id: int,
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    plan = repository.get_asset_plan(asset_plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Asset plan not found.")
    return plan.model_dump(mode="json")


@app.post("/renders/create/{asset_plan_id}")
def create_render(
    asset_plan_id: int,
    request: RenderRequest = Body(default_factory=RenderRequest),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    try:
        service = create_render_workflow_service(
            settings=settings,
            repository=repository,
            mock=request.mock,
        )
        render = service.create_render(asset_plan_id, request)
    except RenderWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return render.model_dump(mode="json")


@app.get("/renders")
def list_renders(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    renders = repository.list_video_renders(status=status, limit=limit)
    return {"renders": [render.model_dump(mode="json") for render in renders]}


@app.get("/renders/{render_id}")
def get_render(
    render_id: int,
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    render = repository.get_video_render(render_id)
    if render is None:
        raise HTTPException(status_code=404, detail="Video render not found.")
    return render.model_dump(mode="json")


@app.post("/renders/validate/{asset_plan_id}")
def validate_render(
    asset_plan_id: int,
    request: RenderRequest = Body(default_factory=RenderRequest),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    try:
        service = create_render_workflow_service(
            settings=settings,
            repository=repository,
            mock=True,
        )
        result = service.validate_asset_plan(asset_plan_id, force=request.force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@app.post("/youtube/prepare-upload/{render_id}")
def prepare_youtube_upload(
    render_id: int,
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    try:
        service = create_youtube_upload_service(
            settings=settings,
            repository=repository,
            mock=True,
        )
        upload = service.prepare_upload(render_id)
    except YouTubeWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return upload.model_dump(mode="json")


@app.post("/youtube/approve-upload/{upload_id}")
def approve_youtube_upload(
    upload_id: int,
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    try:
        service = create_youtube_upload_service(
            settings=settings,
            repository=repository,
            mock=True,
        )
        upload = service.approve_upload(upload_id)
    except YouTubeWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return upload.model_dump(mode="json")


@app.post("/youtube/upload/{upload_id}")
def upload_to_youtube(
    upload_id: int,
    request_context: Request,
    request: YouTubeUploadRequest = Body(default_factory=YouTubeUploadRequest),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    before = repository.get_youtube_upload(upload_id)
    try:
        service = create_youtube_upload_service(
            settings=settings,
            repository=repository,
            mock=request.mock,
        )
        upload = service.upload(upload_id, request)
    except YouTubeWorkflowError as exc:
        _audit_dashboard_attempt(
            settings,
            repository,
            request_context,
            action="youtube_upload_attempt_failed",
            entity_type="youtube_upload",
            entity_id=upload_id,
            before_status=before.status if before else None,
            after_status="upload_failed",
            reason=str(exc),
            metadata={"mock": request.mock},
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _audit_dashboard_attempt(
        settings,
        repository,
        request_context,
        action="youtube_upload_attempt",
        entity_type="youtube_upload",
        entity_id=upload_id,
        before_status=before.status if before else None,
        after_status=upload.status,
        metadata={"mock": request.mock, "privacy_status": upload.privacy_status},
    )
    return upload.model_dump(mode="json")


@app.post("/youtube/schedule/{upload_id}")
def schedule_youtube_upload(
    upload_id: int,
    request: YouTubeScheduleRequest,
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    try:
        service = create_youtube_upload_service(
            settings=settings,
            repository=repository,
            mock=True,
        )
        upload = service.schedule_upload(upload_id, request)
    except (YouTubeWorkflowError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return upload.model_dump(mode="json")


@app.get("/youtube/uploads")
def list_youtube_uploads(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    uploads = repository.list_youtube_uploads(status=status, limit=limit)
    return {"uploads": [upload.model_dump(mode="json") for upload in uploads]}


@app.get("/youtube/uploads/{upload_id}")
def get_youtube_upload(
    upload_id: int,
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    upload = repository.get_youtube_upload(upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="YouTube upload record not found.")
    return upload.model_dump(mode="json")


@app.get("/youtube/metadata-preview/{render_id}")
def youtube_metadata_preview(
    render_id: int,
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    try:
        service = create_youtube_upload_service(
            settings=settings,
            repository=repository,
            mock=True,
        )
        metadata = service.metadata_preview(render_id)
    except YouTubeWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return metadata.model_dump(mode="json")


@app.get("/youtube/oauth-url")
def youtube_oauth_url(settings: Settings = Depends(get_settings)) -> dict:
    try:
        return {"authorization_url": build_oauth_url(settings)}
    except YouTubeOAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/youtube/token-status")
def youtube_token_status(settings: Settings = Depends(get_settings)) -> dict:
    return token_status(settings).model_dump(mode="json")


@app.post("/analytics/fetch/{upload_id}")
def fetch_analytics(
    upload_id: int,
    request: AnalyticsFetchRequest = Body(default_factory=AnalyticsFetchRequest),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    try:
        service = create_analytics_workflow_service(
            settings=settings,
            repository=repository,
            mock=request.mock,
        )
        snapshot = service.fetch_for_upload(upload_id, request)
    except AnalyticsWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return snapshot.model_dump(mode="json")


@app.post("/analytics/fetch-all")
def fetch_all_analytics(
    request: AnalyticsFetchAllRequest = Body(default_factory=AnalyticsFetchAllRequest),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    try:
        service = create_analytics_workflow_service(
            settings=settings,
            repository=repository,
            mock=request.mock,
        )
        snapshots = service.fetch_all(request)
    except AnalyticsWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"snapshots": [snapshot.model_dump(mode="json") for snapshot in snapshots]}


@app.get("/analytics/snapshots")
def list_analytics_snapshots(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    snapshots = repository.list_analytics_snapshots(status=status, limit=limit)
    return {"snapshots": [snapshot.model_dump(mode="json") for snapshot in snapshots]}


@app.get("/analytics/snapshots/{snapshot_id}")
def get_analytics_snapshot(
    snapshot_id: int,
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    snapshot = repository.get_analytics_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Analytics snapshot not found.")
    return snapshot.model_dump(mode="json")


@app.post("/analytics/update-scores")
def update_analytics_scores(
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    scores = StrategyLearningService(
        settings=settings,
        repository=repository,
    ).update_category_scores()
    return {"category_scores": [score.model_dump(mode="json") for score in scores]}


@app.get("/strategy/recommend")
def strategy_recommend(
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    recommendation = StrategyLearningService(settings=settings, repository=repository).recommend()
    return recommendation.model_dump(mode="json")


@app.get("/strategy/categories")
def strategy_categories(
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    scores = StrategyLearningService(settings=settings, repository=repository).categories()
    return {"category_scores": [score.model_dump(mode="json") for score in scores]}


@app.get("/ops/health")
def ops_health(
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    service = WorkflowOrchestrationService(settings=settings, repository=repository)
    queue = service.review_queue()
    latest_runs = repository.list_workflow_runs(limit=1)
    return ops_health_payload(
        settings=settings,
        queue=queue,
        latest_workflow_run=latest_runs[0] if latest_runs else None,
    )


@app.get("/ops/status")
def ops_status(
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    service = WorkflowOrchestrationService(settings=settings, repository=repository)
    return service.status().model_dump(mode="json")


@app.get("/ops/workflow-runs")
def ops_workflow_runs(
    workflow_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    runs = repository.list_workflow_runs(workflow_type=workflow_type, status=status, limit=limit)
    return {"workflow_runs": [run.model_dump(mode="json") for run in runs]}


@app.get("/ops/workflow-runs/{run_id}")
def ops_workflow_run(
    run_id: int,
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    run = repository.get_workflow_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found.")
    return run.model_dump(mode="json")


@app.post("/ops/run/daily-draft")
def ops_run_daily_draft(
    request_context: Request,
    request: WorkflowRequest = Body(default_factory=WorkflowRequest),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    service = WorkflowOrchestrationService(settings=settings, repository=repository)
    run = service.run_daily_draft(request)
    _audit_dashboard_attempt(
        settings,
        repository,
        request_context,
        action="workflow_run_triggered",
        entity_type="workflow_run",
        entity_id=run.id,
        after_status=run.status,
        metadata={"workflow_type": run.workflow_type, "source": "api"},
    )
    return run.model_dump(mode="json")


@app.post("/ops/run/analytics-due")
def ops_run_analytics_due(
    request_context: Request,
    request: WorkflowRequest = Body(default_factory=WorkflowRequest),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    service = WorkflowOrchestrationService(settings=settings, repository=repository)
    run = service.run_analytics_due(request)
    _audit_dashboard_attempt(
        settings,
        repository,
        request_context,
        action="workflow_run_triggered",
        entity_type="workflow_run",
        entity_id=run.id,
        after_status=run.status,
        metadata={"workflow_type": run.workflow_type, "source": "api"},
    )
    return run.model_dump(mode="json")


@app.get("/ops/pending-review")
def ops_pending_review(
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    queue = WorkflowOrchestrationService(settings=settings, repository=repository).review_queue()
    return queue.model_dump(mode="json")


@app.get("/review/queue")
def review_queue(
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    queue = WorkflowOrchestrationService(settings=settings, repository=repository).review_queue()
    return queue.model_dump(mode="json")


@app.get("/audit/logs")
def list_audit_logs(
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    if since or until:
        logs = filtered_audit_logs(
            repository,
            action=action,
            entity_type=entity_type,
            since=since,
            until=until,
            limit=limit,
        )
    else:
        logs = repository.list_audit_logs(
            action=action,
            entity_type=entity_type,
            limit=limit,
            offset=offset,
        )
    return {"audit_logs": [log.model_dump(mode="json") for log in logs]}


@app.get("/audit/export.json")
def export_audit_json_endpoint(
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    logs = filtered_audit_logs(
        repository,
        action=action,
        entity_type=entity_type,
        since=since,
        until=until,
        limit=limit,
    )
    return audit_logs_payload(logs)


@app.get("/audit/export.csv")
def export_audit_csv_endpoint(
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    repository: RaatVerseRepository = Depends(get_repository),
) -> Response:
    logs = filtered_audit_logs(
        repository,
        action=action,
        entity_type=entity_type,
        since=since,
        until=until,
        limit=limit,
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "created_at", "actor", "action", "entity_type", "entity_id", "before_status", "after_status", "reason"])
    for log in logs:
        writer.writerow([
            log.id,
            log.created_at.isoformat(),
            log.actor,
            log.action,
            log.entity_type,
            log.entity_id,
            log.before_status,
            log.after_status,
            log.reason,
        ])
    return Response(buffer.getvalue(), media_type="text/csv")


@app.get("/audit/logs/{audit_log_id}")
def get_audit_log(
    audit_log_id: int,
    repository: RaatVerseRepository = Depends(get_repository),
) -> dict:
    log = repository.get_audit_log(audit_log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Audit log not found.")
    return log.model_dump(mode="json")


@app.post("/dashboard/scripts/{draft_id}/approve")
async def dashboard_approve_script(
    draft_id: int,
    request: Request,
    token: str | None = Query(default=None),
    x_dashboard_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
):
    form = await _form_values(request)
    _check_dashboard_token(
        settings,
        request=request,
        repository=repository,
        token=token,
        header_token=x_dashboard_token,
        form_token=form.get("token"),
        action="dashboard_script_approve",
        entity_type="script_draft",
        entity_id=draft_id,
    )
    comment = form.get("comment", "").strip() or None
    before = repository.get_script_draft(draft_id)
    draft = repository.update_script_draft_status(draft_id, "approved")
    if draft is None:
        raise HTTPException(status_code=404, detail="Script draft not found.")
    _audit_dashboard_attempt(
        settings,
        repository,
        request,
        action="script_approve",
        entity_type="script_draft",
        entity_id=draft_id,
        before_status=before.status if before else None,
        after_status=draft.status,
        reason=comment,
    )
    _record_approval_event(
        settings,
        repository,
        request,
        entity_type="script_draft",
        entity_id=draft_id,
        action="script_approve",
        comment=comment,
    )
    return _redirect_dashboard(settings, token or form.get("token"), f"/dashboard/scripts/{draft_id}")


@app.post("/dashboard/scripts/{draft_id}/reject")
async def dashboard_reject_script(
    draft_id: int,
    request: Request,
    token: str | None = Query(default=None),
    x_dashboard_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
):
    form = await _form_values(request)
    _check_dashboard_token(
        settings,
        request=request,
        repository=repository,
        token=token,
        header_token=x_dashboard_token,
        form_token=form.get("token"),
        action="dashboard_script_reject",
        entity_type="script_draft",
        entity_id=draft_id,
    )
    reason = form.get("reason", "").strip() or "Rejected from dashboard."
    comment = form.get("comment", "").strip() or reason
    before = repository.get_script_draft(draft_id)
    draft = repository.update_script_draft_status(draft_id, "rejected", reason)
    if draft is None:
        raise HTTPException(status_code=404, detail="Script draft not found.")
    _audit_dashboard_attempt(
        settings,
        repository,
        request,
        action="script_reject",
        entity_type="script_draft",
        entity_id=draft_id,
        before_status=before.status if before else None,
        after_status=draft.status,
        reason=reason,
        metadata={"comment": comment} if comment else None,
    )
    _record_approval_event(
        settings,
        repository,
        request,
        entity_type="script_draft",
        entity_id=draft_id,
        action="script_reject",
        comment=comment,
    )
    return _redirect_dashboard(settings, token or form.get("token"), f"/dashboard/scripts/{draft_id}")


@app.post("/dashboard/scripts/{draft_id}/regenerate")
async def dashboard_regenerate_script(
    draft_id: int,
    request: Request,
    token: str | None = Query(default=None),
    x_dashboard_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
):
    form = await _form_values(request)
    _check_dashboard_token(
        settings,
        request=request,
        repository=repository,
        token=token,
        header_token=x_dashboard_token,
        form_token=form.get("token"),
        action="dashboard_script_regenerate",
        entity_type="script_draft",
        entity_id=draft_id,
    )
    comment = form.get("comment", "").strip() or None
    before = repository.get_script_draft(draft_id)
    mock = settings.automation_mode == "mock"
    try:
        generator = create_script_draft_generator(settings, mock=mock)
        service = ScriptDraftService(settings=settings, repository=repository, generator=generator)
        response = service.regenerate_rejected(draft_id)
    except (LLMConfigurationError, LLMProviderError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if response.draft is None:
        raise HTTPException(status_code=400, detail=response.error or response.validation.issues)
    _audit_dashboard_attempt(
        settings,
        repository,
        request,
        action="script_regenerate",
        entity_type="script_draft",
        entity_id=draft_id,
        before_status=before.status if before else None,
        after_status=response.draft.status,
        reason=comment,
        metadata={"new_script_id": response.saved_draft_id, "mock": mock},
    )
    _record_approval_event(
        settings,
        repository,
        request,
        entity_type="script_draft",
        entity_id=draft_id,
        action="script_regenerate",
        comment=comment or f"New draft: {response.saved_draft_id}",
    )
    return _redirect_dashboard(settings, token or form.get("token"), f"/dashboard/scripts/{response.saved_draft_id}")


@app.post("/dashboard/assets/prepare/{script_id}")
async def dashboard_prepare_assets(
    script_id: int,
    request: Request,
    token: str | None = Query(default=None),
    x_dashboard_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
):
    form = await _form_values(request)
    _check_dashboard_token(
        settings,
        request=request,
        repository=repository,
        token=token,
        header_token=x_dashboard_token,
        form_token=form.get("token"),
        action="dashboard_assets_prepare",
        entity_type="script_draft",
        entity_id=script_id,
    )
    note = form.get("note", "").strip() or None
    mock = settings.automation_mode == "mock"
    try:
        service = create_asset_preparation_service(settings=settings, repository=repository, mock=mock)
        plan = service.prepare_for_script(script_id, AssetPreparationRequest(mock=mock))
    except (AssetWorkflowError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _audit_dashboard_attempt(
        settings,
        repository,
        request,
        action="assets_prepare",
        entity_type="asset_plan",
        entity_id=plan.id,
        after_status=plan.status,
        reason=note,
        metadata={"script_id": script_id, "mock": mock},
    )
    _record_approval_event(
        settings,
        repository,
        request,
        entity_type="asset_plan",
        entity_id=plan.id,
        action="assets_prepare",
        comment=note,
    )
    return _redirect_dashboard(settings, token or form.get("token"))


@app.post("/dashboard/renders/create/{asset_plan_id}")
async def dashboard_create_render(
    asset_plan_id: int,
    request: Request,
    token: str | None = Query(default=None),
    x_dashboard_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
):
    form = await _form_values(request)
    _check_dashboard_token(
        settings,
        request=request,
        repository=repository,
        token=token,
        header_token=x_dashboard_token,
        form_token=form.get("token"),
        action="dashboard_render_create",
        entity_type="asset_plan",
        entity_id=asset_plan_id,
    )
    note = form.get("note", "").strip() or None
    mock = settings.automation_mode == "mock"
    try:
        service = create_render_workflow_service(settings=settings, repository=repository, mock=mock)
        render = service.create_render(asset_plan_id, RenderRequest(mock=mock))
    except (RenderWorkflowError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _audit_dashboard_attempt(
        settings,
        repository,
        request,
        action="render_create",
        entity_type="video_render",
        entity_id=render.id,
        after_status=render.status,
        reason=note,
        metadata={"asset_plan_id": asset_plan_id, "mock": mock},
    )
    _record_approval_event(
        settings,
        repository,
        request,
        entity_type="video_render",
        entity_id=render.id,
        action="render_create",
        comment=note,
    )
    return _redirect_dashboard(settings, token or form.get("token"))


@app.post("/dashboard/youtube/prepare-upload/{render_id}")
async def dashboard_prepare_youtube_upload(
    render_id: int,
    request: Request,
    token: str | None = Query(default=None),
    x_dashboard_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
):
    form = await _form_values(request)
    _check_dashboard_token(
        settings,
        request=request,
        repository=repository,
        token=token,
        header_token=x_dashboard_token,
        form_token=form.get("token"),
        action="dashboard_youtube_prepare_upload",
        entity_type="video_render",
        entity_id=render_id,
    )
    note = form.get("note", "").strip() or None
    try:
        service = create_youtube_upload_service(settings=settings, repository=repository, mock=True)
        upload = service.prepare_upload(render_id)
    except YouTubeWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _audit_dashboard_attempt(
        settings,
        repository,
        request,
        action="youtube_prepare_upload",
        entity_type="youtube_upload",
        entity_id=upload.id,
        after_status=upload.status,
        reason=note,
        metadata={"render_id": render_id},
    )
    _record_approval_event(
        settings,
        repository,
        request,
        entity_type="youtube_upload",
        entity_id=upload.id,
        action="youtube_prepare_upload",
        comment=note,
    )
    return _redirect_dashboard(settings, token or form.get("token"))


@app.post("/dashboard/youtube/approve-upload/{upload_id}")
async def dashboard_approve_youtube_upload(
    upload_id: int,
    request: Request,
    token: str | None = Query(default=None),
    x_dashboard_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
):
    form = await _form_values(request)
    _check_dashboard_token(
        settings,
        request=request,
        repository=repository,
        token=token,
        header_token=x_dashboard_token,
        form_token=form.get("token"),
        action="dashboard_youtube_approve_upload",
        entity_type="youtube_upload",
        entity_id=upload_id,
    )
    comment = form.get("comment", "").strip() or None
    before = repository.get_youtube_upload(upload_id)
    try:
        service = create_youtube_upload_service(settings=settings, repository=repository, mock=True)
        upload = service.approve_upload(upload_id)
    except YouTubeWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _audit_dashboard_attempt(
        settings,
        repository,
        request,
        action="youtube_approve_upload",
        entity_type="youtube_upload",
        entity_id=upload_id,
        before_status=before.status if before else None,
        after_status=upload.status,
        reason=comment,
    )
    _record_approval_event(
        settings,
        repository,
        request,
        entity_type="youtube_upload",
        entity_id=upload_id,
        action="youtube_approve_upload",
        comment=comment,
    )
    return _redirect_dashboard(settings, token or form.get("token"))


@app.post("/dashboard/workflow/daily-draft")
def dashboard_run_daily_draft(
    request: Request,
    token: str | None = Query(default=None),
    x_dashboard_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
):
    _check_dashboard_token(
        settings,
        request=request,
        repository=repository,
        token=token,
        header_token=x_dashboard_token,
        action="dashboard_workflow_daily_draft",
        entity_type="workflow",
    )
    service = WorkflowOrchestrationService(settings=settings, repository=repository)
    run = service.run_daily_draft(WorkflowRequest(mock=settings.automation_mode == "mock"))
    _audit_dashboard_attempt(
        settings,
        repository,
        request,
        action="workflow_run_triggered",
        entity_type="workflow_run",
        entity_id=run.id,
        after_status=run.status,
        metadata={"workflow_type": run.workflow_type},
    )
    return _redirect_dashboard(settings, token)


@app.post("/dashboard/workflow/analytics-due")
def dashboard_run_analytics_due(
    request: Request,
    token: str | None = Query(default=None),
    x_dashboard_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
):
    _check_dashboard_token(
        settings,
        request=request,
        repository=repository,
        token=token,
        header_token=x_dashboard_token,
        action="dashboard_workflow_analytics_due",
        entity_type="workflow",
    )
    service = WorkflowOrchestrationService(settings=settings, repository=repository)
    run = service.run_analytics_due(WorkflowRequest(mock=settings.automation_mode == "mock"))
    _audit_dashboard_attempt(
        settings,
        repository,
        request,
        action="workflow_run_triggered",
        entity_type="workflow_run",
        entity_id=run.id,
        after_status=run.status,
        metadata={"workflow_type": run.workflow_type},
    )
    return _redirect_dashboard(settings, token)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    token: str | None = Query(default=None),
    script_status: str | None = Query(default=None),
    script_category: str | None = Query(default=None),
    q: str | None = Query(default=None),
    upload_status: str | None = Query(default=None),
    workflow_status: str | None = Query(default=None),
    workflow_type: str | None = Query(default=None),
    audit_action: str | None = Query(default=None),
    audit_entity_type: str | None = Query(default=None),
    x_dashboard_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> HTMLResponse:
    _check_dashboard_token(
        settings,
        request=request,
        repository=repository,
        token=token,
        header_token=x_dashboard_token,
        read=True,
    )
    service = WorkflowOrchestrationService(settings=settings, repository=repository)
    queue = service.review_queue()
    status = service.status()
    drafts = _filter_drafts(
        repository.list_script_drafts(status=script_status, limit=100),
        category=script_category,
        query=q,
    )[:20]
    assets = repository.list_asset_plans(limit=8)
    renders = repository.list_video_renders(limit=5)
    uploads = repository.list_youtube_uploads(status=upload_status, limit=20)
    runs = repository.list_workflow_runs(
        workflow_type=workflow_type,
        status=workflow_status,
        limit=20,
    )
    snapshots = repository.list_analytics_snapshots(limit=5)
    audit_logs = repository.list_audit_logs(
        action=audit_action,
        entity_type=audit_entity_type,
        limit=20,
    )
    approval_events = repository.list_approval_events(limit=20)
    recommendation = StrategyLearningService(settings=settings, repository=repository).recommend()
    token_query = (
        f"?token={escape(token or settings.dashboard_admin_token)}"
        if settings.dashboard_require_token or settings.dashboard_protect_reads
        else ""
    )
    html = f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>RaatVerse Operations</title>
        <style>
          * {{ box-sizing: border-box; }}
          body {{ font-family: system-ui, sans-serif; margin: 0; background: #10100f; color: #eee; }}
          main {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
          a {{ color: #8fd3ff; }}
          section {{ margin-bottom: 24px; }}
          .hero {{ border-bottom: 1px solid #333; background: #181715; padding: 18px 20px; position: sticky; top: 0; z-index: 2; }}
          .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
          .panel {{ border: 1px solid #2e2a25; background: #171614; padding: 14px; border-radius: 8px; }}
          table {{ width: 100%; border-collapse: collapse; background: #181818; }}
          th, td {{ border-bottom: 1px solid #333; padding: 8px; text-align: left; }}
          th {{ color: #cfc3a3; font-size: 13px; }}
          .pill {{ display: inline-block; padding: 2px 8px; border: 1px solid #555; border-radius: 999px; margin-right: 6px; }}
          form {{ display: inline; }}
          button {{ background: #d7b56d; color: #10100f; border: 0; padding: 6px 9px; border-radius: 6px; font-weight: 700; cursor: pointer; }}
          input {{ background: #0f0f0e; color: #eee; border: 1px solid #555; padding: 6px; border-radius: 6px; max-width: 180px; }}
          select {{ background: #0f0f0e; color: #eee; border: 1px solid #555; padding: 6px; border-radius: 6px; max-width: 180px; }}
          .muted {{ color: #aaa; }}
          .filters {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: end; }}
          .filters label {{ display: grid; gap: 3px; color: #cfc3a3; font-size: 12px; }}
          @media (max-width: 720px) {{ main {{ padding: 12px; }} table {{ font-size: 13px; }} th:nth-child(4), td:nth-child(4) {{ display: none; }} }}
        </style>
      </head>
      <body>
        <div class="hero">
          <h1>RaatVerse Review Console</h1>
          <span class="pill">Mode: {escape(status.automation_mode)}</span>
          <span class="pill">Auto upload: {status.auto_upload}</span>
          <span class="pill">Pending review: {queue.total_pending}</span>
          <span class="pill">Token required: {settings.dashboard_require_token}</span>
        </div>
        <main>
          <section class="panel">
            <p>{escape(recommendation.summary)}</p>
            {_post_button("/dashboard/workflow/daily-draft", "Run Daily Draft", token_query)}
            {_post_button("/dashboard/workflow/analytics-due", "Run Analytics Due", token_query)}
          </section>
          <section class="panel">
            <h2>Filters</h2>
            <form method="get" action="/dashboard" class="filters">
              {_token_hidden(settings, token)}
              <label>Script status <input name="script_status" value="{escape(script_status or '')}"></label>
              <label>Category <input name="script_category" value="{escape(script_category or '')}"></label>
              <label>Search <input name="q" value="{escape(q or '')}"></label>
              <label>Upload status <input name="upload_status" value="{escape(upload_status or '')}"></label>
              <label>Workflow type <input name="workflow_type" value="{escape(workflow_type or '')}"></label>
              <label>Workflow status <input name="workflow_status" value="{escape(workflow_status or '')}"></label>
              <label>Audit action <input name="audit_action" value="{escape(audit_action or '')}"></label>
              <label>Audit entity <input name="audit_entity_type" value="{escape(audit_entity_type or '')}"></label>
              <button type="submit">Apply</button>
            </form>
          </section>
          <div class="grid">
            <div class="panel">{_review_table("Scripts Pending Review", queue.scripts_pending_review, token_query)}</div>
            <div class="panel">{_review_table("Rejected Scripts", queue.rejected_scripts, token_query)}</div>
            <div class="panel">{_action_table("Approved Scripts Needing Assets", queue.scripts_approved_needing_assets, "Prepare Assets", "/dashboard/assets/prepare", "id", token_query)}</div>
            <div class="panel">{_action_table("Assets Ready Needing Render", queue.assets_ready_needing_render, "Render", "/dashboard/renders/create", "id", token_query)}</div>
            <div class="panel">{_action_table("Renders Needing Upload Metadata", queue.renders_ready_needing_upload_prepare, "Prepare Upload", "/dashboard/youtube/prepare-upload", "id", token_query)}</div>
            <div class="panel">{_action_table("Uploads Pending Approval", queue.uploads_pending_approval, "Approve Upload", "/dashboard/youtube/approve-upload", "id", token_query)}</div>
          </div>
          {_table("Latest Drafts", [_script_row(draft, token_query) for draft in drafts], ["id", "status", "category", "title", "actions"])}
          {_table("Latest Asset Plans", [plan.model_dump(mode="json") for plan in assets], ["id", "status", "script_draft_id", "provider"])}
          {_table("Latest Renders", [render.model_dump(mode="json") for render in renders], ["id", "status", "renderer_provider", "output_path"])}
          {_table("Latest Uploads", [upload.model_dump(mode="json") for upload in uploads], ["id", "status", "privacy_status", "title"])}
          {_table("Latest Analytics", [snapshot.model_dump(mode="json") for snapshot in snapshots], ["id", "snapshot_window", "views", "performance_score"])}
          {_table("Recent Workflow Runs", [run.model_dump(mode="json") for run in runs], ["id", "workflow_type", "status", "provider_mode"])}
          {_table("Recent Approval History", [event.model_dump(mode="json") for event in approval_events], ["id", "actor", "action", "entity_type", "entity_id", "comment"])}
          {_table("Recent Audit Logs", [log.model_dump(mode="json") for log in audit_logs], ["id", "actor", "action", "entity_type", "entity_id", "after_status"])}
        </main>
      </body>
    </html>
    """
    return HTMLResponse(html)


@app.get("/dashboard/scripts/{draft_id}", response_class=HTMLResponse)
def dashboard_script_detail(
    draft_id: int,
    request: Request,
    token: str | None = Query(default=None),
    x_dashboard_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    repository: RaatVerseRepository = Depends(get_repository),
) -> HTMLResponse:
    _check_dashboard_token(
        settings,
        request=request,
        repository=repository,
        token=token,
        header_token=x_dashboard_token,
        read=True,
        entity_type="script_draft",
        entity_id=draft_id,
    )
    draft = repository.get_script_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Script draft not found.")
    history = repository.list_approval_events(entity_type="script_draft", entity_id=draft_id, limit=20)
    token_query = (
        f"?token={escape(token or settings.dashboard_admin_token)}"
        if settings.dashboard_require_token or settings.dashboard_protect_reads
        else ""
    )
    reject_action = f"/dashboard/scripts/{draft_id}/reject{token_query}"
    approve_action = f"/dashboard/scripts/{draft_id}/approve{token_query}"
    regenerate_action = f"/dashboard/scripts/{draft_id}/regenerate{token_query}"
    html = f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{escape(draft.title)} | RaatVerse</title>
        <style>
          body {{ font-family: system-ui, sans-serif; margin: 0; background: #10100f; color: #eee; }}
          main {{ max-width: 900px; margin: 0 auto; padding: 20px; }}
          a {{ color: #8fd3ff; }}
          pre {{ white-space: pre-wrap; background: #181818; padding: 14px; border-radius: 8px; }}
          button {{ background: #d7b56d; color: #10100f; border: 0; padding: 8px 10px; border-radius: 6px; font-weight: 700; cursor: pointer; }}
          input {{ background: #0f0f0e; color: #eee; border: 1px solid #555; padding: 8px; border-radius: 6px; min-width: 260px; }}
          form {{ display: inline-block; margin: 4px 6px 4px 0; }}
        </style>
      </head>
      <body>
        <main>
          <p><a href="{_dashboard_url(settings, token)}">Back to dashboard</a></p>
          <h1>{escape(draft.title)}</h1>
          <p>{escape(draft.category)} / {escape(draft.story_type)} | status: {escape(draft.status)}</p>
          <form method="post" action="{approve_action}">
            {_token_hidden(settings, token)}
            <input name="comment" placeholder="Approval comment">
            <button type="submit">Approve Script</button>
          </form>
          <form method="post" action="{regenerate_action}">
            {_token_hidden(settings, token)}
            <input name="comment" placeholder="Regeneration note">
            <button type="submit">Regenerate Rejected</button>
          </form>
          <form method="post" action="{reject_action}">
            {_token_hidden(settings, token)}
            <input name="reason" value="Needs revision before approval.">
            <input name="comment" placeholder="Optional review note">
            <button type="submit">Reject</button>
          </form>
          {_table("Approval History", [event.model_dump(mode="json") for event in history], ["id", "actor", "action", "comment", "created_at"])}
          <h2>Hook</h2>
          <pre>{escape(draft.hook)}</pre>
          <h2>Narration</h2>
          <pre>{escape(draft.narration_script)}</pre>
        </main>
      </body>
    </html>
    """
    return HTMLResponse(html)


def _table(title: str, rows: list[dict], columns: list[str]) -> str:
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    if not rows:
        body = f"<tr><td colspan='{len(columns)}'>None</td></tr>"
    else:
        body = "".join(
            "<tr>"
            + "".join(
                f"<td>{str(row.get(column, '')) if column == 'actions' else escape(str(row.get(column, '')))}</td>"
                for column in columns
            )
            + "</tr>"
            for row in rows
        )
    return f"<section><h2>{escape(title)}</h2><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></section>"


def _post_button(action: str, label: str, token_query: str = "") -> str:
    return f'<form method="post" action="{escape(action + token_query)}"><button type="submit">{escape(label)}</button></form>'


def _token_hidden(settings: Settings, token: str | None = None) -> str:
    if not (settings.dashboard_require_token or settings.dashboard_protect_reads):
        return ""
    resolved = token or settings.dashboard_admin_token
    return f'<input type="hidden" name="token" value="{escape(resolved)}">' if resolved else ""


def _script_row(draft, token_query: str) -> dict:
    actions = f'<a href="{escape(f"/dashboard/scripts/{draft.id}{token_query}")}">Open</a>'
    return {
        "id": draft.id,
        "status": draft.status,
        "category": draft.category,
        "title": draft.title,
        "actions": actions,
    }


def _review_table(title: str, rows: list[dict], token_query: str) -> str:
    enriched = []
    for row in rows:
        copy = dict(row)
        script_url = f"/dashboard/scripts/{row.get('id')}{token_query}"
        copy["actions"] = f'<a href="{escape(script_url)}">Review</a>'
        enriched.append(copy)
    return _table(title, enriched, ["id", "status", "category", "title", "actions"])


def _action_table(
    title: str,
    rows: list[dict],
    label: str,
    action_prefix: str,
    id_key: str,
    token_query: str,
) -> str:
    enriched = []
    for row in rows:
        copy = dict(row)
        copy["actions"] = _post_button(f"{action_prefix}/{row.get(id_key)}", label, token_query)
        enriched.append(copy)
    return _table(title, enriched, ["id", "status", "title", "actions"])


def _filter_drafts(drafts: list, *, category: str | None, query: str | None) -> list:
    filtered = drafts
    if category:
        normalized_category = category.lower()
        filtered = [draft for draft in filtered if draft.category.lower() == normalized_category]
    if query:
        needle = query.lower()
        filtered = [
            draft
            for draft in filtered
            if needle in draft.title.lower()
            or needle in draft.hook.lower()
            or needle in draft.category.lower()
            or needle in draft.story_type.lower()
        ]
    return filtered
