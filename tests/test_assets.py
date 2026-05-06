import os
import subprocess
import sys

import pytest

from raatverse_agent.assets.errors import AssetWorkflowError, StockMediaProviderError
from raatverse_agent.assets.media import PexelsStockMediaProvider, PixabayStockMediaProvider
from raatverse_agent.assets.models import AssetPlan, AssetPreparationRequest, MediaAssetCandidate, TTSGenerationRequest
from raatverse_agent.assets.quality import analyze_asset_plan, score_visual_relevance, select_diverse_media_candidates
from raatverse_agent.assets.service import (
    create_asset_preparation_service,
    create_tts_asset_service,
)
from raatverse_agent.assets.timing import build_subtitle_timings, build_tts_aligned_subtitle_timings
from raatverse_agent.assets.tts import EdgeFreeTTSProvider
from raatverse_agent.assets.tts_text import (
    build_cta_tts_text,
    chunk_tts_text,
    is_cta_tts_chunk,
    normalize_tts_text,
    prepare_tts_text,
)
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
    assert audio.tts_text
    assert audio.tts_quality_metadata["chunk_count"] >= 1


def test_tts_text_normalization_and_chunking_preserves_text(tmp_path):
    settings = _settings(tmp_path, tts_max_chars_per_chunk=90)
    text = "Raat gehri thi... aur main akela tha.\n\nDarwaza mat khol."

    normalized = normalize_tts_text(text, settings)
    chunks = chunk_tts_text(normalized, settings.tts_max_chars_per_chunk)

    assert "..." not in normalized
    assert chunks
    assert all(len(chunk) <= settings.tts_max_chars_per_chunk for chunk in chunks)
    assert "".join("".join(chunks).split()) == "".join(normalized.split())


def test_devanagari_tts_text_selection_for_hindi_voice(tmp_path):
    settings = _settings(tmp_path, tts_voice="hi-IN-SwaraNeural", tts_use_devanagari=True)
    draft_id = _create_draft(settings, approved=True)

    with session_scope(settings.database_url) as session:
        draft = RaatVerseRepository(session).get_script_draft(draft_id)

    prepared = prepare_tts_text(draft, settings)

    assert "रात" in prepared.tts_text
    assert "दरवाजा" in prepared.tts_text or "दरवाज़ा" in prepared.tts_text
    assert prepared.input_characters > 0


def test_cta_tts_normalization_uses_clear_subscribe_phrase(tmp_path):
    settings = _settings(tmp_path, tts_voice="hi-IN-SwaraNeural", tts_use_devanagari=True)
    draft_id = _create_draft(settings, approved=True)

    with session_scope(settings.database_url) as session:
        draft = RaatVerseRepository(session).get_script_draft(draft_id)

    prepared = prepare_tts_text(draft, settings)

    assert "\u0938\u092c\u094d\u0938\u0915\u094d\u0930\u093e\u0907\u092c \u091c\u093c\u0930\u0942\u0930 \u0915\u0930\u0947\u0902" in prepared.tts_text
    assert prepared.cta_tts_mode == "auto"
    assert is_cta_tts_chunk(prepared.chunks[-1], build_cta_tts_text(settings))


def test_cta_tts_override_is_used_only_for_tts_text(tmp_path):
    override = "\u0930\u093e\u0924\u0935\u0930\u094d\u0938 \u0915\u094b \u0938\u092c\u094d\u0938\u0915\u094d\u0930\u093e\u0907\u092c \u0915\u0930\u0947\u0902\u0964"
    settings = _settings(tmp_path, cta_tts_override=override)
    draft_id = _create_draft(settings, approved=True)

    with session_scope(settings.database_url) as session:
        draft = RaatVerseRepository(session).get_script_draft(draft_id)

    prepared = prepare_tts_text(draft, settings)

    assert override in prepared.tts_text
    assert settings.outro_cta in draft.narration_script
    assert prepared.cta_tts_mode == "override"


def test_subtitle_alignment_uses_boundary_events_when_available(tmp_path):
    settings = _settings(tmp_path, subtitle_global_offset_seconds=0.0)
    draft_id = _create_draft(settings, approved=True)

    with session_scope(settings.database_url) as session:
        draft = RaatVerseRepository(session).get_script_draft(draft_id)

    chunks = ["पहला हिस्सा।", "अंत में सब्सक्राइब ज़रूर करें।"]
    metadata = {
        "tts_chunk_timings": [
            {"chunk_index": 0, "text": chunks[0], "start_second": 0.0, "end_second": 8.0},
            {"chunk_index": 1, "text": chunks[1], "start_second": 8.0, "end_second": 12.0},
        ],
        "edge_boundary_events": [
            {"chunk_index": 0, "start_second": 0.2, "end_second": 1.0, "text": "पहला"},
            {"chunk_index": 1, "start_second": 8.3, "end_second": 9.0, "text": "सब्सक्राइब"},
        ],
    }

    timings, diagnostics = build_tts_aligned_subtitle_timings(
        draft=draft,
        duration_seconds=12,
        settings=settings,
        tts_text=" ".join(chunks),
        tts_chunks=chunks,
        tts_quality_metadata=metadata,
    )

    assert timings
    assert diagnostics["mode_used"] == "boundary_first"
    assert diagnostics["boundary_aligned_lines"] > 0
    assert min(item.start_second for item in timings) >= 0.2


def test_subtitle_alignment_fallback_estimates_from_chunks(tmp_path):
    settings = _settings(tmp_path, subtitle_global_offset_seconds=0.0)
    draft_id = _create_draft(settings, approved=True)

    with session_scope(settings.database_url) as session:
        draft = RaatVerseRepository(session).get_script_draft(draft_id)

    timings, diagnostics = build_tts_aligned_subtitle_timings(
        draft=draft,
        duration_seconds=18,
        settings=settings,
        tts_text="story chunk subscribe chunk",
        tts_chunks=["story chunk", "subscribe chunk"],
        tts_quality_metadata={},
    )

    assert timings
    assert diagnostics["mode_used"] == "chunk_estimate"
    assert diagnostics["fallback_aligned_lines"] == len(timings)
    assert timings[0].start_second >= 0


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
    assert len({item.source_url for item in plan.media_assets}) == len(plan.media_assets)


def test_media_duplicate_filter_prefers_unique_vertical_assets(tmp_path):
    settings = _settings(tmp_path, stock_media_results_per_beat=3)
    candidates = [
        MediaAssetCandidate(
            provider="pexels",
            query="same",
            media_type="video",
            source_url="https://stock.example/reused.mp4",
            width=1080,
            height=1920,
            beat_index=0,
            score=1.0,
        ),
        MediaAssetCandidate(
            provider="pexels",
            query="same",
            media_type="video",
            source_url="https://stock.example/reused.mp4",
            width=1080,
            height=1920,
            beat_index=1,
            score=1.0,
        ),
        MediaAssetCandidate(
            provider="pexels",
            query="unique",
            media_type="video",
            source_url="https://stock.example/unique-1.mp4",
            width=1080,
            height=1920,
            beat_index=1,
            score=0.8,
        ),
    ]

    selected = select_diverse_media_candidates(candidates, beat_count=2, settings=settings)

    assert len(selected) == 2
    assert len({item.source_url for item in selected}) == 2


def test_asset_quality_report_flags_repeated_and_weak_media(tmp_path):
    settings = _settings(tmp_path)
    plan = AssetPlan(
        id=7,
        script_draft_id=1,
        provider="pexels",
        media_assets=[
            MediaAssetCandidate(
                provider="pexels",
                query="dark room",
                media_type="video",
                source_url="https://stock.example/reused.mp4",
                width=1920,
                height=1080,
                beat_index=0,
                score=1.0,
            ),
            MediaAssetCandidate(
                provider="pexels",
                query="dark hall",
                media_type="video",
                source_url="https://stock.example/reused.mp4",
                width=1920,
                height=1080,
                beat_index=1,
                score=1.0,
            ),
        ],
    )

    report = analyze_asset_plan(plan, settings)

    assert report.asset_plan_id == 7
    assert report.repeated_urls == ["https://stock.example/reused.mp4"]
    assert report.vertical_media_count == 0
    assert report.weak_beats == [0, 1]


def test_visual_relevance_scoring_uses_scene_metadata(tmp_path):
    settings = _settings(tmp_path)
    draft_id = _create_draft(settings, approved=True)

    with session_scope(settings.database_url) as session:
        draft = RaatVerseRepository(session).get_script_draft(draft_id)
    beat = draft.scene_beats[1]
    strong = MediaAssetCandidate(
        provider="pexels",
        query="dark narrow corridor wet floor footprints night vertical suspense",
        media_type="video",
        source_url="https://stock.example/corridor.mp4",
        width=1080,
        height=1920,
        beat_index=1,
        score=1.0,
    )
    weak = MediaAssetCandidate(
        provider="pexels",
        query="bright beach sunset happy travel",
        media_type="video",
        source_url="https://stock.example/beach.mp4",
        width=1920,
        height=1080,
        beat_index=1,
        score=1.0,
    )

    assert score_visual_relevance(strong, settings, beat) > score_visual_relevance(weak, settings, beat)


def test_asset_alignment_report_includes_per_beat_details(tmp_path):
    settings = _settings(tmp_path)
    draft_id = _create_draft(settings, approved=True)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        draft = repository.get_script_draft(draft_id)
        service = create_asset_preparation_service(settings=settings, repository=repository, mock=True)
        plan = service.prepare_for_script(draft_id, AssetPreparationRequest(mock=True))
        report = analyze_asset_plan(plan, settings, draft)

    assert report.beat_alignments
    assert report.beat_alignments[-1].is_cta_outro is True
    assert report.beat_alignments[-1].duration_allocated >= settings.cta_min_duration_seconds


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
    quality = subprocess.run([*base, "assets", "quality", "1"], check=True, env=full_env, capture_output=True, text=True)

    assert "Audio ID:" in tts.stdout
    assert "Asset plan ID:" in assets.stdout
    assert "asset quality report" in assets.stdout.lower()
    assert "Unique media URLs:" in quality.stdout
