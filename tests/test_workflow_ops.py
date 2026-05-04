import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from raatverse_agent.assets.models import AssetPreparationRequest
from raatverse_agent.assets.service import create_asset_preparation_service
from raatverse_agent.config import Settings
from raatverse_agent.db.models import YouTubeUploadRecord
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.db.session import initialize_database, session_scope
from raatverse_agent.ops.lock import WorkflowLock
from raatverse_agent.ops.models import WorkflowRequest
from raatverse_agent.ops.workflow import WorkflowOrchestrationService
from raatverse_agent.rendering.models import RenderRequest
from raatverse_agent.rendering.service import create_render_workflow_service
from raatverse_agent.script_generation.models import ScriptGenerationRequest
from raatverse_agent.script_generation.service import ScriptDraftService
from raatverse_agent.services.mock import MockDraftScriptGenerator
from raatverse_agent.youtube.models import YouTubeUploadRequest
from raatverse_agent.youtube.service import create_youtube_upload_service


def _settings(tmp_path, **overrides):
    values = {
        "database_url": f"sqlite:///{(tmp_path / 'workflow.db').as_posix()}",
        "tts_cache_dir": str(tmp_path / "outputs" / "assets" / "audio"),
        "stock_media_cache_dir": str(tmp_path / "outputs" / "assets" / "media"),
        "render_output_dir": str(tmp_path / "outputs" / "renders"),
        "workflow_log_dir": str(tmp_path / "outputs" / "logs"),
        "youtube_token_file": str(tmp_path / "secrets" / "youtube_token.json"),
        "llm_provider": "mock",
        "tts_provider": "mock",
        "stock_media_provider": "mock",
        "video_renderer": "mock",
        "automation_mode": "mock",
        "script_categories_csv": "horror,mystery,suspense",
        "story_categories_csv": "horror,mystery,suspense",
    }
    values.update(overrides)
    return Settings(**values)


def _create_uploaded_record(settings: Settings) -> int:
    initialize_database(settings.database_url)
    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        script_service = ScriptDraftService(
            settings=settings,
            repository=repository,
            generator=MockDraftScriptGenerator(settings),
        )
        response = script_service.generate(ScriptGenerationRequest(category="horror", mock=True))
        draft_id = response.saved_draft_id
        repository.update_script_draft_status(draft_id, "approved")
        asset_service = create_asset_preparation_service(settings=settings, repository=repository, mock=True)
        plan = asset_service.prepare_for_script(draft_id, AssetPreparationRequest(mock=True))
        render_service = create_render_workflow_service(settings=settings, repository=repository, mock=True)
        render = render_service.create_render(plan.id, RenderRequest(mock=True))
        youtube_service = create_youtube_upload_service(settings=settings, repository=repository, mock=True)
        upload = youtube_service.prepare_upload(render.id)
        youtube_service.approve_upload(upload.id)
        uploaded = youtube_service.upload(upload.id, YouTubeUploadRequest(mock=True))
    return uploaded.id


def test_daily_draft_workflow_stops_at_review(tmp_path):
    settings = _settings(tmp_path)
    initialize_database(settings.database_url)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = WorkflowOrchestrationService(settings=settings, repository=repository)
        run = service.run_daily_draft(WorkflowRequest(mock=True))
        drafts = repository.list_script_drafts()
        plans = repository.list_asset_plans()

    assert run.status == "success"
    assert run.created_script_id is not None
    assert run.created_asset_plan_id is None
    assert len(drafts) == 1
    assert drafts[0].status in {"draft", "needs_revision"}
    assert plans == []


def test_full_mock_workflow_completes_safe_private_path(tmp_path):
    settings = _settings(tmp_path)
    initialize_database(settings.database_url)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = WorkflowOrchestrationService(settings=settings, repository=repository)
        run = service.run_full_mock()
        upload = repository.get_youtube_upload(run.created_upload_id)
        snapshots = repository.list_analytics_snapshots()

    assert run.status == "success"
    assert run.created_script_id is not None
    assert run.created_asset_plan_id is not None
    assert run.created_render_id is not None
    assert run.created_upload_id is not None
    assert upload.status == "upload_private"
    assert upload.privacy_status == "private"
    assert len(snapshots) == 1


def test_workflow_run_persistence_and_latest_by_type(tmp_path):
    settings = _settings(tmp_path)
    initialize_database(settings.database_url)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = WorkflowOrchestrationService(settings=settings, repository=repository)
        run = service.run_daily_draft(WorkflowRequest(mock=True))
        listed = repository.list_workflow_runs()
        shown = repository.get_workflow_run(run.id)
        latest = repository.get_latest_workflow_run_by_type("daily_draft")

    assert len(listed) == 1
    assert shown.id == run.id
    assert latest.id == run.id


def test_lock_prevents_duplicate_run_and_stale_lock_is_cleared(tmp_path):
    settings = _settings(tmp_path)
    initialize_database(settings.database_url)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = WorkflowOrchestrationService(settings=settings, repository=repository)
        with WorkflowLock(settings, "daily-draft"):
            skipped = service.run_daily_draft(WorkflowRequest(mock=True))

    assert skipped.status == "skipped"
    assert "locked" in (skipped.error_message or "")

    lock_path = Path(settings.workflow_log_dir) / "locks" / "daily-draft.lock"
    old = datetime.now(timezone.utc) - timedelta(minutes=settings.scheduler_lock_timeout_minutes + 5)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps({"created_at": old.isoformat()}), encoding="utf-8")

    with WorkflowLock(settings, "daily-draft") as lock:
        assert lock.acquired is True
    assert not lock_path.exists()


def test_analytics_due_workflow_fetches_due_windows(tmp_path):
    settings = _settings(tmp_path)
    upload_id = _create_uploaded_record(settings)
    initialize_database(settings.database_url)

    with session_scope(settings.database_url) as session:
        record = session.get(YouTubeUploadRecord, upload_id)
        record.updated_at = datetime.now(timezone.utc) - timedelta(days=2, hours=1)
        session.commit()

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = WorkflowOrchestrationService(settings=settings, repository=repository)
        run = service.run_analytics_due(WorkflowRequest(mock=True))
        snapshots = repository.list_analytics_snapshots()

    assert run.status == "success"
    assert run.summary["snapshots_created"] == 2
    assert {snapshot.snapshot_window for snapshot in snapshots} == {"24h", "48h"}


def test_review_queue_reports_human_actions(tmp_path):
    settings = _settings(tmp_path)
    initialize_database(settings.database_url)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = WorkflowOrchestrationService(settings=settings, repository=repository)
        service.run_daily_draft(WorkflowRequest(mock=True))
        queue = service.review_queue()

    assert queue.total_pending >= 1
    assert len(queue.pending_script_drafts) == 1


def test_github_actions_workflows_exist_and_are_safe():
    daily = Path(".github/workflows/daily-draft.yml").read_text(encoding="utf-8")
    analytics = Path(".github/workflows/analytics-sync.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch" in daily
    assert "workflow_dispatch" in analytics
    assert "--mock" in daily
    assert "--mock" in analytics
    assert "AUTO_UPLOAD: \"false\"" in daily
    assert "AUTO_UPLOAD: \"false\"" in analytics
    assert "youtube upload" not in daily.lower()


def test_scheduler_config_defaults_are_safe():
    settings = Settings()

    assert settings.automation_mode == "mock"
    assert settings.daily_stop_after_draft is True
    assert settings.auto_prepare_assets is False
    assert settings.auto_render is False
    assert settings.auto_prepare_upload is False
    assert settings.auto_upload is False
    assert settings.auto_upload_must_be_approved is True


def test_cli_workflow_and_review_commands(tmp_path):
    db_file = tmp_path / "cli-workflow.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_file.as_posix()}",
        "LLM_PROVIDER": "mock",
        "TTS_PROVIDER": "mock",
        "STOCK_MEDIA_PROVIDER": "mock",
        "VIDEO_RENDERER": "mock",
        "AUTOMATION_MODE": "mock",
        "WORKFLOW_LOG_DIR": str(tmp_path / "logs"),
        "TTS_CACHE_DIR": str(tmp_path / "audio"),
        "STOCK_MEDIA_CACHE_DIR": str(tmp_path / "media"),
        "RENDER_OUTPUT_DIR": str(tmp_path / "renders"),
    }
    base = [sys.executable, "-m", "raatverse_agent"]

    subprocess.run([*base, "db", "init"], check=True, env=env)
    draft = subprocess.run(
        [*base, "workflow", "daily-draft", "--mock"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    queue = subprocess.run(
        [*base, "review", "queue"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    runs = subprocess.run(
        [*base, "workflow", "runs"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    status = subprocess.run(
        [*base, "workflow", "status"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    assert "daily_draft" in draft.stdout
    assert "review queue" in queue.stdout
    assert "daily_draft" in runs.stdout
    assert "operations status" in status.stdout
