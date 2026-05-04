import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from raatverse_agent.analytics.models import AnalyticsFetchRequest, AnalyticsSnapshot, CategoryScoreSummary
from raatverse_agent.analytics.scoring import enrich_snapshot_scores
from raatverse_agent.analytics.service import create_analytics_workflow_service
from raatverse_agent.analytics.strategy import StrategyLearningService
from raatverse_agent.assets.models import AssetPreparationRequest
from raatverse_agent.assets.service import create_asset_preparation_service
from raatverse_agent.config import Settings
from raatverse_agent.db.models import YouTubeUploadRecord
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.db.session import initialize_database, session_scope
from raatverse_agent.rendering.models import RenderRequest
from raatverse_agent.rendering.service import create_render_workflow_service
from raatverse_agent.script_generation.models import ScriptGenerationRequest
from raatverse_agent.script_generation.service import ScriptDraftService
from raatverse_agent.services.mock import MockDraftScriptGenerator
from raatverse_agent.youtube.models import YouTubeUploadRequest
from raatverse_agent.youtube.service import create_youtube_upload_service


def _settings(tmp_path, **overrides):
    values = {
        "database_url": f"sqlite:///{(tmp_path / 'analytics.db').as_posix()}",
        "tts_cache_dir": str(tmp_path / "outputs" / "assets" / "audio"),
        "stock_media_cache_dir": str(tmp_path / "outputs" / "assets" / "media"),
        "render_output_dir": str(tmp_path / "outputs" / "renders"),
        "youtube_token_file": str(tmp_path / "secrets" / "youtube_token.json"),
        "llm_provider": "mock",
        "tts_provider": "mock",
        "stock_media_provider": "mock",
        "video_renderer": "mock",
        "script_categories_csv": "horror,mystery,suspense",
        "story_categories_csv": "horror,mystery,suspense",
        "youtube_client_id": "",
        "youtube_client_secret": "",
        "youtube_refresh_token": "",
    }
    values.update(overrides)
    return Settings(**values)


def _create_uploaded_record(settings: Settings, category: str = "horror") -> int:
    initialize_database(settings.database_url)
    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        script_service = ScriptDraftService(
            settings=settings,
            repository=repository,
            generator=MockDraftScriptGenerator(settings),
        )
        response = script_service.generate(ScriptGenerationRequest(category=category, mock=True))
        draft_id = response.saved_draft_id
        repository.update_script_draft_status(draft_id, "approved")
        asset_service = create_asset_preparation_service(
            settings=settings,
            repository=repository,
            mock=True,
        )
        plan = asset_service.prepare_for_script(draft_id, AssetPreparationRequest(mock=True))
        render_service = create_render_workflow_service(
            settings=settings,
            repository=repository,
            mock=True,
        )
        render = render_service.create_render(plan.id, RenderRequest(mock=True))
        youtube_service = create_youtube_upload_service(
            settings=settings,
            repository=repository,
            mock=True,
        )
        upload = youtube_service.prepare_upload(render.id)
        youtube_service.approve_upload(upload.id)
        uploaded = youtube_service.upload(upload.id, YouTubeUploadRequest(mock=True))
    return uploaded.id


def test_mock_analytics_fetch_persists_snapshot(tmp_path):
    settings = _settings(tmp_path)
    upload_id = _create_uploaded_record(settings)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = create_analytics_workflow_service(
            settings=settings,
            repository=repository,
            mock=True,
        )
        snapshot = service.fetch_for_upload(
            upload_id,
            AnalyticsFetchRequest(mock=True, snapshot_window="24h"),
        )
        listed = repository.list_analytics_snapshots()
        shown = repository.get_analytics_snapshot(snapshot.id)

    assert snapshot.status == "snapshot_ready"
    assert snapshot.views > 0
    assert snapshot.like_rate > 0
    assert snapshot.performance_score > 0
    assert len(listed) == 1
    assert shown.id == snapshot.id


def test_missing_analytics_scope_is_saved_as_graceful_failed_snapshot(tmp_path):
    settings = _settings(
        tmp_path,
        youtube_scopes="https://www.googleapis.com/auth/youtube.upload",
    )
    upload_id = _create_uploaded_record(settings)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = create_analytics_workflow_service(
            settings=settings,
            repository=repository,
            mock=False,
        )
        snapshot = service.fetch_for_upload(upload_id, AnalyticsFetchRequest(mock=False))

    assert snapshot.status == "snapshot_failed"
    assert "YOUTUBE_SCOPES" in snapshot.error_message


def test_scoring_formula_normalizes_against_channel_average(tmp_path):
    settings = _settings(tmp_path)
    previous = AnalyticsSnapshot(
        youtube_upload_id=1,
        youtube_video_id="v1",
        script_draft_id=1,
        category="horror",
        story_type="atmospheric_horror",
        views=100,
        likes=5,
        comments=1,
        average_view_duration=20,
        subscribers_gained=1,
        like_rate=0.05,
        comment_rate=0.01,
        performance_score=45,
    )
    current = AnalyticsSnapshot(
        youtube_upload_id=2,
        youtube_video_id="v2",
        script_draft_id=2,
        category="horror",
        story_type="atmospheric_horror",
        snapshot_window="48h",
        views=250,
        likes=25,
        comments=6,
        average_view_duration=45,
        subscribers_gained=3,
    )

    scored = enrich_snapshot_scores(settings, current, [previous], category_video_count=2)

    assert scored.like_rate == 0.1
    assert scored.comment_rate == 0.024
    assert scored.retention_score > previous.average_view_duration
    assert scored.performance_score > previous.performance_score
    assert scored.confidence > 0


def test_category_score_update_and_strategy_recommendation(tmp_path):
    settings = _settings(tmp_path)
    initialize_database(settings.database_url)
    now = datetime.now(timezone.utc)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        repository.create_analytics_snapshot(
            AnalyticsSnapshot(
                youtube_upload_id=1,
                youtube_video_id="mock-horror",
                script_draft_id=1,
                category="horror",
                story_type="atmospheric_horror",
                snapshot_window="48h",
                snapshot_date=now,
                views=1000,
                likes=95,
                comments=18,
                average_view_duration=48,
                subscribers_gained=6,
                like_rate=0.095,
                comment_rate=0.018,
                performance_score=82,
                confidence=0.8,
            )
        )
        repository.create_analytics_snapshot(
            AnalyticsSnapshot(
                youtube_upload_id=2,
                youtube_video_id="mock-mystery",
                script_draft_id=2,
                category="mystery",
                story_type="locked_room",
                snapshot_window="48h",
                snapshot_date=now,
                views=300,
                likes=12,
                comments=2,
                average_view_duration=28,
                subscribers_gained=1,
                like_rate=0.04,
                comment_rate=0.006,
                performance_score=42,
                confidence=0.65,
            )
        )
        service = StrategyLearningService(settings=settings, repository=repository)
        scores = service.update_category_scores()
        recommendation = service.recommend()

    assert scores[0].category == "horror"
    assert scores[0].avg_performance_score == 82
    assert recommendation.next_category == "horror"
    assert any(item.category == "horror" for item in recommendation.weekly_distribution)


def test_auto_category_generation_uses_category_scores(tmp_path):
    settings = _settings(tmp_path)
    initialize_database(settings.database_url)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        repository.init_category_scores(settings.all_categories)
        repository.upsert_category_score_summary(
            CategoryScoreSummary(
                category="horror",
                total_videos=4,
                avg_views=900,
                avg_likes=80,
                avg_performance_score=78,
                confidence=0.8,
            )
        )
        repository.upsert_category_score_summary(
            CategoryScoreSummary(
                category="mystery",
                total_videos=4,
                avg_views=300,
                avg_likes=15,
                avg_performance_score=35,
                confidence=0.6,
            )
        )
        service = ScriptDraftService(
            settings=settings,
            repository=repository,
            generator=MockDraftScriptGenerator(settings),
        )
        response = service.generate(ScriptGenerationRequest(auto_category=True, mock=True))

    assert response.draft is not None
    assert response.draft.category == "horror"


def test_due_snapshot_detection(tmp_path):
    settings = _settings(tmp_path)
    upload_id = _create_uploaded_record(settings)

    with session_scope(settings.database_url) as session:
        record = session.get(YouTubeUploadRecord, upload_id)
        record.updated_at = datetime.now(timezone.utc) - timedelta(days=2, hours=2)
        session.commit()

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = create_analytics_workflow_service(
            settings=settings,
            repository=repository,
            mock=True,
        )
        due = service.due_snapshots()

    assert len(due) == 1
    assert "24h" in due[0].due_windows
    assert "48h" in due[0].due_windows
    assert "7d" not in due[0].due_windows


def test_cli_analytics_mock_workflow(tmp_path):
    db_file = tmp_path / "cli-analytics.db"
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
    subprocess.run([*base, "youtube", "prepare-upload", "1"], check=True, env=env)
    subprocess.run([*base, "youtube", "approve-upload", "1"], check=True, env=env)
    subprocess.run([*base, "youtube", "upload", "1", "--mock"], check=True, env=env)
    fetched = subprocess.run(
        [*base, "analytics", "fetch", "1", "--mock"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    scores = subprocess.run(
        [*base, "analytics", "update-scores"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    recommendation = subprocess.run(
        [*base, "strategy", "recommend"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    auto_draft = subprocess.run(
        [*base, "script", "generate", "--auto-category", "--mock"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    assert "analytics snapshot" in fetched.stdout
    assert "horror" in scores.stdout
    assert "strategy recommendation" in recommendation.stdout
    assert "script draft generated" in auto_draft.stdout
