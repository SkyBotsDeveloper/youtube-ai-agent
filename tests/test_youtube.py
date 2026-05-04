import os
import subprocess
import sys
from pathlib import Path

from raatverse_agent.assets.models import AssetPreparationRequest
from raatverse_agent.assets.service import create_asset_preparation_service
from raatverse_agent.config import Settings
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.db.session import initialize_database, session_scope
from raatverse_agent.rendering.models import RenderRequest
from raatverse_agent.rendering.service import create_render_workflow_service
from raatverse_agent.script_generation.models import ScriptGenerationRequest
from raatverse_agent.script_generation.service import ScriptDraftService
from raatverse_agent.services.mock import MockDraftScriptGenerator
from raatverse_agent.youtube.metadata import generate_youtube_metadata
from raatverse_agent.youtube.models import YouTubeScheduleRequest, YouTubeUploadRequest
from raatverse_agent.youtube.oauth import build_oauth_url, token_status
from raatverse_agent.youtube.service import YouTubeUploadWorkflowService, create_youtube_upload_service
from raatverse_agent.youtube.uploader import YouTubeDataApiUploader


def _settings(tmp_path, **overrides):
    values = {
        "database_url": f"sqlite:///{(tmp_path / 'youtube.db').as_posix()}",
        "tts_cache_dir": str(tmp_path / "outputs" / "assets" / "audio"),
        "stock_media_cache_dir": str(tmp_path / "outputs" / "assets" / "media"),
        "render_output_dir": str(tmp_path / "outputs" / "renders"),
        "youtube_token_file": str(tmp_path / "secrets" / "youtube_token.json"),
        "llm_provider": "mock",
        "tts_provider": "mock",
        "stock_media_provider": "mock",
        "video_renderer": "mock",
        "script_categories_csv": "horror,mystery",
        "story_categories_csv": "horror,mystery",
        "youtube_client_id": "",
        "youtube_client_secret": "",
        "youtube_refresh_token": "",
    }
    values.update(overrides)
    return Settings(**values)


def _create_render(settings: Settings, *, approve_script: bool = True):
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
        if approve_script:
            repository.update_script_draft_status(draft_id, "approved")
        asset_service = create_asset_preparation_service(
            settings=settings,
            repository=repository,
            mock=True,
        )
        plan = asset_service.prepare_for_script(
            draft_id,
            AssetPreparationRequest(mock=True, force=not approve_script),
        )
        render_service = create_render_workflow_service(
            settings=settings,
            repository=repository,
            mock=True,
        )
        render = render_service.create_render(
            plan.id,
            RenderRequest(mock=True, force=not approve_script),
        )
    return render.id


def test_prepare_upload_creates_metadata_and_persists(tmp_path):
    settings = _settings(tmp_path)
    render_id = _create_render(settings)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = create_youtube_upload_service(settings=settings, repository=repository, mock=True)
        upload = service.prepare_upload(render_id)
        listed = repository.list_youtube_uploads()
        shown = repository.get_youtube_upload(upload.id)

    assert upload.status == "upload_pending"
    assert upload.privacy_status == "private"
    assert upload.category_id == "24"
    assert "RaatVerse" in upload.tags
    assert len(listed) == 1
    assert shown is not None
    assert shown.id == upload.id


def test_cannot_prepare_upload_for_non_ready_render(tmp_path):
    settings = _settings(tmp_path)
    render_id = _create_render(settings)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        repository.update_video_render_status(render_id, "render_failed", error_message="broken")
        service = create_youtube_upload_service(settings=settings, repository=repository, mock=True)
        try:
            service.prepare_upload(render_id)
        except Exception as exc:
            error = str(exc)
        else:
            error = ""

    assert "render_ready" in error


def test_cannot_upload_without_approval_then_mock_private_upload(tmp_path):
    settings = _settings(tmp_path)
    render_id = _create_render(settings)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = create_youtube_upload_service(settings=settings, repository=repository, mock=True)
        pending = service.prepare_upload(render_id)
        blocked = None
        try:
            service.upload(pending.id, YouTubeUploadRequest(mock=True))
        except Exception as exc:
            blocked = str(exc)
        approved = service.approve_upload(pending.id)
        uploaded = service.upload(approved.id, YouTubeUploadRequest(mock=True))

    assert "explicitly approved" in blocked
    assert uploaded.status == "upload_private"
    assert uploaded.youtube_video_id.startswith("mock-")
    assert uploaded.youtube_url.startswith("https://www.youtube.com/watch")


def test_scheduled_publish_metadata_validation_and_mock_upload(tmp_path):
    settings = _settings(tmp_path)
    render_id = _create_render(settings)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = create_youtube_upload_service(settings=settings, repository=repository, mock=True)
        upload = service.prepare_upload(render_id)
        scheduled = service.schedule_upload(
            upload.id,
            YouTubeScheduleRequest(publish_at="2026-05-05T20:00:00+05:30"),
        )
        service.approve_upload(upload.id)
        uploaded = service.upload(upload.id, YouTubeUploadRequest(mock=True))

    assert scheduled.privacy_status == "private"
    assert scheduled.scheduled_publish_at is not None
    assert uploaded.status == "upload_scheduled"


def test_missing_oauth_credentials_graceful_error(tmp_path):
    settings = _settings(tmp_path)
    render_id = _create_render(settings)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        mock_service = create_youtube_upload_service(settings=settings, repository=repository, mock=True)
        upload = mock_service.prepare_upload(render_id)
        mock_service.approve_upload(upload.id)
        real_service = YouTubeUploadWorkflowService(
            settings=settings,
            repository=repository,
            uploader=YouTubeDataApiUploader(settings),
        )
        failed = real_service.upload(upload.id, YouTubeUploadRequest(mock=False))

    assert failed.status == "upload_failed"
    assert "No YouTube refresh token" in (failed.error_message or "")


def test_metadata_generation_contains_safe_defaults(tmp_path):
    settings = _settings(tmp_path)
    render_id = _create_render(settings)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        render = repository.get_video_render(render_id)
        draft = repository.get_script_draft(render.script_draft_id)
        plan = repository.get_asset_plan(render.asset_plan_id)
        metadata = generate_youtube_metadata(
            settings=settings,
            draft=draft,
            render=render,
            asset_plan=plan,
        )

    assert metadata.privacy_status == "private"
    assert metadata.self_declared_made_for_kids is False
    assert metadata.contains_synthetic_media is True
    assert len(metadata.title) <= 100
    assert "#Shorts" in metadata.description


def test_oauth_url_token_status_and_gitignore_safety(tmp_path):
    settings = _settings(
        tmp_path,
        youtube_client_id="client-id",
        youtube_client_secret="client-secret",
    )

    url = build_oauth_url(settings)
    status = token_status(settings)
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    assert "accounts.google.com" in url
    assert "youtube.upload" in url
    assert status.token_file_exists is False
    assert "secrets/" in gitignore
    assert "*_token.json" in gitignore


def test_cli_youtube_mock_workflow(tmp_path):
    db_file = tmp_path / "cli-youtube.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_file.as_posix()}",
        "LLM_PROVIDER": "mock",
        "TTS_PROVIDER": "mock",
        "STOCK_MEDIA_PROVIDER": "mock",
        "VIDEO_RENDERER": "mock",
        "TTS_CACHE_DIR": str(tmp_path / "audio"),
        "STOCK_MEDIA_CACHE_DIR": str(tmp_path / "media"),
        "RENDER_OUTPUT_DIR": str(tmp_path / "renders"),
        "YOUTUBE_TOKEN_FILE": str(tmp_path / "secrets" / "youtube_token.json"),
    }
    base = [sys.executable, "-m", "raatverse_agent"]

    subprocess.run([*base, "db", "init"], check=True, env=env)
    subprocess.run([*base, "script", "generate", "--category", "horror", "--mock"], check=True, env=env)
    subprocess.run([*base, "script", "approve", "1"], check=True, env=env)
    subprocess.run([*base, "assets", "prepare", "1", "--mock"], check=True, env=env)
    subprocess.run([*base, "render", "create", "1", "--mock"], check=True, env=env)
    preview = subprocess.run(
        [*base, "youtube", "metadata-preview", "1"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    prepare = subprocess.run(
        [*base, "youtube", "prepare-upload", "1"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    subprocess.run([*base, "youtube", "approve-upload", "1"], check=True, env=env)
    uploaded = subprocess.run(
        [*base, "youtube", "upload", "1", "--mock"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    listed = subprocess.run(
        [*base, "youtube", "list"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    assert "metadata preview" in preview.stdout
    assert "Upload ID: 1" in prepare.stdout
    assert "upload_private" in uploaded.stdout
    assert "upload_private" in listed.stdout
