import os
import subprocess
import sys

import pytest

from raatverse_agent.assets.errors import AssetWorkflowError, StockMediaProviderError
from raatverse_agent.assets.media import PexelsStockMediaProvider, PixabayStockMediaProvider
from raatverse_agent.assets.models import AssetPreparationRequest, TTSGenerationRequest
from raatverse_agent.assets.service import (
    create_asset_preparation_service,
    create_tts_asset_service,
)
from raatverse_agent.assets.timing import build_subtitle_timings
from raatverse_agent.assets.tts import EdgeFreeTTSProvider
from raatverse_agent.config import Settings
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.db.session import initialize_database, session_scope
from raatverse_agent.script_generation.models import ScriptGenerationRequest
from raatverse_agent.script_generation.service import ScriptDraftService
from raatverse_agent.services.mock import MockDraftScriptGenerator


def _settings(tmp_path, **overrides):
    values = {
        "database_url": f"sqlite:///{(tmp_path / 'assets.db').as_posix()}",
        "tts_cache_dir": str(tmp_path / "outputs" / "assets" / "audio"),
        "stock_media_cache_dir": str(tmp_path / "outputs" / "assets" / "media"),
        "script_categories_csv": "horror,mystery",
        "story_categories_csv": "horror,mystery",
        "stock_media_results_per_beat": 2,
    }
    values.update(overrides)
    return Settings(**values)


def _create_draft(settings: Settings, *, approved: bool = True):
    initialize_database(settings.database_url)
    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = ScriptDraftService(
            settings=settings,
            repository=repository,
            generator=MockDraftScriptGenerator(settings),
        )
        response = service.generate(ScriptGenerationRequest(category="horror", mock=True))
        assert response.draft is not None
        draft_id = response.saved_draft_id
        if approved:
            repository.update_script_draft_status(draft_id, "approved")
    return draft_id


def test_mock_tts_generation_for_approved_script(tmp_path):
    settings = _settings(tmp_path)
    draft_id = _create_draft(settings, approved=True)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = create_tts_asset_service(settings=settings, repository=repository, mock=True)
        audio = service.generate_for_script(draft_id, TTSGenerationRequest(mock=True))

    assert audio.status == "asset_ready"
    assert audio.provider == "mock"
    assert audio.file_path is not None
    assert audio.duration_seconds and audio.duration_seconds > 0
    assert len(audio.subtitle_timings) > 0


def test_free_tts_provider_returns_failed_metadata_when_network_fails(monkeypatch, tmp_path):
    settings = _settings(tmp_path, tts_provider="free")
    draft_id = _create_draft(settings, approved=True)

    def fail_generate_audio(self, draft):
        from raatverse_agent.assets.errors import TTSProviderError

        raise TTSProviderError("network unavailable")

    monkeypatch.setattr(EdgeFreeTTSProvider, "generate_audio", fail_generate_audio)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = create_tts_asset_service(settings=settings, repository=repository, mock=False)
        audio = service.generate_for_script(draft_id, TTSGenerationRequest(mock=False))

    assert audio.status == "asset_failed"
    assert "network unavailable" in (audio.error_message or "")


def test_subtitle_timing_generation(tmp_path):
    settings = _settings(tmp_path)
    draft_id = _create_draft(settings, approved=True)

    with session_scope(settings.database_url) as session:
        draft = RaatVerseRepository(session).get_script_draft(draft_id)

    timings = build_subtitle_timings(draft)

    assert timings
    assert timings[0].start_second == 0
    assert timings[-1].end_second <= draft.estimated_duration_seconds


def test_mock_media_asset_planning(tmp_path):
    settings = _settings(tmp_path)
    draft_id = _create_draft(settings, approved=True)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = create_asset_preparation_service(settings=settings, repository=repository, mock=True)
        plan = service.prepare_for_script(draft_id, AssetPreparationRequest(mock=True))

    assert plan.status == "asset_ready"
    assert plan.audio_asset_id is not None
    assert len(plan.media_assets) >= 1
    assert all(item.provider == "mock" for item in plan.media_assets)


def test_pexels_and_pixabay_missing_keys_fail_gracefully(tmp_path):
    settings = _settings(tmp_path, pexels_api_key="", pixabay_api_key="")
    draft_id = _create_draft(settings, approved=True)

    with session_scope(settings.database_url) as session:
        draft = RaatVerseRepository(session).get_script_draft(draft_id)

    with pytest.raises(StockMediaProviderError, match="PEXELS_API_KEY"):
        PexelsStockMediaProvider(settings).search_for_draft(draft)
    with pytest.raises(StockMediaProviderError, match="PIXABAY_API_KEY"):
        PixabayStockMediaProvider(settings).search_for_draft(draft)


def test_asset_preparation_requires_approved_script_unless_forced(tmp_path):
    settings = _settings(tmp_path)
    draft_id = _create_draft(settings, approved=False)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = create_asset_preparation_service(settings=settings, repository=repository, mock=True)
        with pytest.raises(AssetWorkflowError, match="must be approved"):
            service.prepare_for_script(draft_id, AssetPreparationRequest(mock=True))

        forced = service.prepare_for_script(draft_id, AssetPreparationRequest(mock=True, force=True))

    assert forced.status == "asset_ready"


def test_rejected_draft_regeneration_creates_new_draft(tmp_path):
    settings = _settings(tmp_path)
    draft_id = _create_draft(settings, approved=False)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        rejected = repository.update_script_draft_status(draft_id, "rejected", "Too predictable.")
        service = ScriptDraftService(
            settings=settings,
            repository=repository,
            generator=MockDraftScriptGenerator(settings),
        )
        response = service.regenerate_rejected(rejected.id)
        drafts = repository.list_script_drafts()

    assert response.draft is not None
    assert response.saved_draft_id != draft_id
    assert len(drafts) == 2


def test_cli_tts_and_assets_commands(tmp_path):
    db_file = tmp_path / "cli.db"
    env = {
        "DATABASE_URL": f"sqlite:///{db_file.as_posix()}",
        "TTS_CACHE_DIR": str(tmp_path / "audio"),
        "STOCK_MEDIA_CACHE_DIR": str(tmp_path / "media"),
        "LLM_PROVIDER": "mock",
        "TTS_PROVIDER": "mock",
        "STOCK_MEDIA_PROVIDER": "mock",
    }
    base = [sys.executable, "-m", "raatverse_agent"]

    full_env = {**os.environ, **env}
    subprocess.run([*base, "db", "init"], check=True, env=full_env)
    subprocess.run([*base, "script", "generate", "--category", "horror", "--mock"], check=True, env=full_env)
    subprocess.run([*base, "script", "approve", "1"], check=True, env=full_env)
    tts = subprocess.run([*base, "tts", "generate", "1", "--mock"], check=True, env=full_env, capture_output=True, text=True)
    assets = subprocess.run([*base, "assets", "prepare", "1", "--mock"], check=True, env=full_env, capture_output=True, text=True)

    assert "Audio ID:" in tts.stdout
    assert "Asset plan ID:" in assets.stdout
