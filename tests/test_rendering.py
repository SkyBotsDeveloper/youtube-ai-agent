import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy.orm.attributes import flag_modified

from raatverse_agent.assets.models import AssetPreparationRequest
from raatverse_agent.assets.service import create_asset_preparation_service
from raatverse_agent.assets.timing import align_asset_plan_timing_to_audio
from raatverse_agent.config import Settings
from raatverse_agent.db.models import AssetPlanRecord, AudioAssetRecord
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.db.session import initialize_database, session_scope
from raatverse_agent.rendering.errors import RenderWorkflowError
from raatverse_agent.rendering.formatting import format_video_render
from raatverse_agent.rendering.models import RenderRequest
from raatverse_agent.rendering.renderers import outro_screen_drawtext, watermark_drawtext
from raatverse_agent.rendering.service import create_render_workflow_service
from raatverse_agent.rendering.subtitles import build_ass_subtitles
from raatverse_agent.script_generation.models import ScriptGenerationRequest
from raatverse_agent.script_generation.service import ScriptDraftService
from raatverse_agent.services.mock import MockDraftScriptGenerator


def _settings(tmp_path, **overrides):
    values = {
        "database_url": f"sqlite:///{(tmp_path / 'rendering.db').as_posix()}",
        "tts_cache_dir": str(tmp_path / "outputs" / "assets" / "audio"),
        "stock_media_cache_dir": str(tmp_path / "outputs" / "assets" / "media"),
        "render_output_dir": str(tmp_path / "outputs" / "renders"),
        "llm_provider": "mock",
        "tts_provider": "mock",
        "stock_media_provider": "mock",
        "video_renderer": "mock",
        "script_categories_csv": "horror,mystery",
        "story_categories_csv": "horror,mystery",
    }
    values.update(overrides)
    return Settings(**values)


def _create_asset_plan(settings: Settings, *, approved: bool = True, force_assets: bool = False):
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
        if approved:
            repository.update_script_draft_status(draft_id, "approved")
        asset_service = create_asset_preparation_service(
            settings=settings,
            repository=repository,
            mock=True,
        )
        plan = asset_service.prepare_for_script(
            draft_id,
            AssetPreparationRequest(mock=True, force=force_assets),
        )
    return draft_id, plan.id


def test_mock_render_creation_and_db_persistence(tmp_path):
    settings = _settings(tmp_path)
    _, asset_plan_id = _create_asset_plan(settings, approved=True)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = create_render_workflow_service(settings=settings, repository=repository, mock=True)
        render = service.create_render(asset_plan_id, RenderRequest(mock=True))
        listed = repository.list_video_renders()
        shown = repository.get_video_render(render.id)

    assert render.status == "render_ready"
    assert render.output_path is not None
    assert Path(render.output_path).exists()
    assert render.resolution == "1080x1920"
    assert len(listed) == 1
    assert shown is not None
    assert shown.id == render.id


def test_render_workflow_refuses_unapproved_script(tmp_path):
    settings = _settings(tmp_path)
    _, asset_plan_id = _create_asset_plan(settings, approved=False, force_assets=True)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = create_render_workflow_service(settings=settings, repository=repository, mock=True)
        with pytest.raises(RenderWorkflowError, match="approved"):
            service.create_render(asset_plan_id, RenderRequest(mock=True))


def test_render_workflow_accepts_approved_asset_plan(tmp_path):
    settings = _settings(tmp_path)
    _, asset_plan_id = _create_asset_plan(settings, approved=True)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = create_render_workflow_service(settings=settings, repository=repository, mock=True)
        validation = service.validate_asset_plan(asset_plan_id)

    assert validation.is_valid is True


def test_cta_duration_reservation_and_audio_timing_scaling(tmp_path):
    settings = _settings(tmp_path, cta_min_duration_seconds=7, min_scene_beat_duration_seconds=2.5)
    _, asset_plan_id = _create_asset_plan(settings, approved=True)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        plan = repository.get_asset_plan(asset_plan_id)
        draft = repository.get_script_draft(plan.script_draft_id)
        audio = repository.get_audio_asset(plan.audio_asset_id)
        source_duration = max(item.end_second for item in plan.scene_timings)
        audio = audio.model_copy(update={"duration_seconds": source_duration + 20})
        aligned, report = align_asset_plan_timing_to_audio(
            draft=draft,
            asset_plan=plan,
            audio_asset=audio,
            settings=settings,
        )

    assert report["timing_scaled_to_audio"] is True
    assert report["cta_duration_seconds"] >= settings.cta_min_duration_seconds
    assert aligned.scene_timings[-1].end_second >= audio.duration_seconds
    assert aligned.scene_timings[-1].end_second - aligned.scene_timings[-1].start_second >= settings.cta_min_duration_seconds
    assert min(item.end_second - item.start_second for item in aligned.scene_timings) >= settings.min_scene_beat_duration_seconds


def test_subtitle_duration_enforcement_and_outro_visibility(tmp_path):
    settings = _settings(tmp_path, min_subtitle_duration_seconds=1.2, cta_min_duration_seconds=7)
    _, asset_plan_id = _create_asset_plan(settings, approved=True)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        plan = repository.get_asset_plan(asset_plan_id)
        draft = repository.get_script_draft(plan.script_draft_id)
        audio = repository.get_audio_asset(plan.audio_asset_id)
        aligned, report = align_asset_plan_timing_to_audio(
            draft=draft,
            asset_plan=plan,
            audio_asset=audio,
            settings=settings,
        )

    assert report["subtitle_count"] == len(aligned.subtitle_timings)
    assert min(item.end_second - item.start_second for item in aligned.subtitle_timings) >= settings.min_subtitle_duration_seconds
    assert "Kal raat ek aur nayi kahani milegi." in aligned.subtitle_timings[-1].text


def test_subtitle_offset_application_uses_config(tmp_path):
    settings = _settings(
        tmp_path,
        subtitle_global_offset_seconds=0.35,
        subtitle_end_padding_seconds=0.15,
    )
    _, asset_plan_id = _create_asset_plan(settings, approved=True)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        plan = repository.get_asset_plan(asset_plan_id)
        draft = repository.get_script_draft(plan.script_draft_id)
        audio = repository.get_audio_asset(plan.audio_asset_id)
        aligned, report = align_asset_plan_timing_to_audio(
            draft=draft,
            asset_plan=plan,
            audio_asset=audio,
            settings=settings,
        )

    assert aligned.subtitle_timings[0].start_second >= settings.subtitle_global_offset_seconds
    assert report["subtitle_global_offset_seconds"] == settings.subtitle_global_offset_seconds
    assert report["subtitle_end_padding_seconds"] == settings.subtitle_end_padding_seconds
    assert report["subtitle_timing_source"] in {
        "actual_audio_duration_with_offset",
        "estimated_duration_with_offset",
        "edge_boundary_events_with_offset",
    }


def test_render_preflight_quality_warnings_and_strict_block(tmp_path):
    settings = _settings(tmp_path)
    _, asset_plan_id = _create_asset_plan(settings, approved=True)

    with session_scope(settings.database_url) as session:
        record = session.get(AssetPlanRecord, asset_plan_id)
        assert record is not None
        media = list(record.media_assets_json or [])
        for item in media:
            item["source_url"] = "https://stock.example/reused.mp4"
            item["width"] = 1920
            item["height"] = 1080
        record.media_assets_json = media
        flag_modified(record, "media_assets_json")
        if record.audio_asset_id:
            audio = session.get(AudioAssetRecord, record.audio_asset_id)
            assert audio is not None
            audio.duration_seconds = 999.0
        session.commit()

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = create_render_workflow_service(settings=settings, repository=repository, mock=True)
        validation = service.validate_asset_plan(asset_plan_id)
        strict_validation = service.validate_asset_plan(asset_plan_id, strict_quality=True)

    assert validation.is_valid is True
    assert any("Repeated media URLs" in warning for warning in validation.warnings)
    assert any("Audio duration exceeds" in warning for warning in validation.warnings)
    assert strict_validation.is_valid is False
    assert any("Strict quality check failed" in issue for issue in strict_validation.issues)


def test_render_timing_report_is_persisted(tmp_path):
    settings = _settings(tmp_path)
    _, asset_plan_id = _create_asset_plan(settings, approved=True)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = create_render_workflow_service(settings=settings, repository=repository, mock=True)
        render = service.create_render(asset_plan_id, RenderRequest(mock=True))
        shown = repository.get_video_render(render.id)

    assert shown.timing_report["cta_duration_seconds"] >= settings.cta_min_duration_seconds
    assert shown.timing_report["final_video_duration_seconds"] == render.duration_seconds
    assert shown.timing_report["subtitle_count"] > 0
    assert shown.timing_report["subtitle_global_offset_seconds"] == settings.subtitle_global_offset_seconds
    assert shown.timing_report["cta_outro_screen_enabled"] is True
    assert shown.timing_report["cta_subscribe_button_enabled"] is True


def test_render_timing_report_format_includes_new_cta_fields(tmp_path):
    settings = _settings(tmp_path)
    _, asset_plan_id = _create_asset_plan(settings, approved=True)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = create_render_workflow_service(settings=settings, repository=repository, mock=True)
        render = service.create_render(asset_plan_id, RenderRequest(mock=True))

    formatted = format_video_render(render)

    assert "Subtitle offset used:" in formatted
    assert "CTA TTS mode:" in formatted
    assert "CTA subscribe button enabled: True" in formatted


def test_ass_subtitle_file_generation(tmp_path):
    settings = _settings(tmp_path)
    _, asset_plan_id = _create_asset_plan(settings, approved=True)

    with session_scope(settings.database_url) as session:
        plan = RaatVerseRepository(session).get_asset_plan(asset_plan_id)

    ass_path = build_ass_subtitles(
        timings=plan.subtitle_timings,
        output_path=tmp_path / "captions.ass",
        settings=settings,
    )
    content = ass_path.read_text(encoding="utf-8")

    assert "[V4+ Styles]" in content
    assert "RaatVerseShorts" in content
    assert "Dialogue:" in content


def test_watermark_config_behavior(tmp_path):
    settings = _settings(tmp_path, watermark_text="RV", watermark_position="bottom-right")
    draw = watermark_drawtext(settings)

    assert "text='RV'" in draw
    assert "x=w-tw-48" in draw
    assert "y=h-th-160" in draw


def test_outro_subscribe_button_render_config(tmp_path):
    settings = _settings(tmp_path, outro_subscribe_button_enabled=True)
    draw = outro_screen_drawtext(settings)

    assert "drawbox=" in draw
    assert "text='Subscribe'" in draw
    assert "0xE62117" in draw

    disabled = outro_screen_drawtext(_settings(tmp_path, outro_subscribe_button_enabled=False))
    assert "drawbox=" not in disabled


def test_ffmpeg_missing_graceful_error(tmp_path):
    settings = _settings(
        tmp_path,
        video_renderer="ffmpeg",
        ffmpeg_binary="definitely_missing_ffmpeg_binary",
    )
    _, asset_plan_id = _create_asset_plan(settings, approved=True)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = create_render_workflow_service(settings=settings, repository=repository, mock=False)
        render = service.create_render(asset_plan_id, RenderRequest(mock=False))

    assert render.status == "render_failed"
    assert "FFmpeg binary" in (render.error_message or "")


def test_cli_render_commands(tmp_path):
    db_file = tmp_path / "cli-render.db"
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
    }
    base = [sys.executable, "-m", "raatverse_agent"]

    subprocess.run([*base, "db", "init"], check=True, env=env)
    subprocess.run([*base, "script", "generate", "--category", "horror", "--mock"], check=True, env=env)
    subprocess.run([*base, "script", "approve", "1"], check=True, env=env)
    subprocess.run([*base, "assets", "prepare", "1", "--mock"], check=True, env=env)
    validate = subprocess.run(
        [*base, "render", "validate", "1"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    create = subprocess.run(
        [*base, "render", "create", "1", "--mock"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    listed = subprocess.run(
        [*base, "render", "list"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    assert "Valid: True" in validate.stdout
    assert "Render ID:" in create.stdout
    assert "render_ready" in listed.stdout
