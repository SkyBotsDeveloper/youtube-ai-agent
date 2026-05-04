from __future__ import annotations

from raatverse_agent.assets.models import AssetPlan, AudioAsset


def format_audio_asset(audio: AudioAsset) -> str:
    return (
        "RaatVerse narration audio generated\n"
        f"Audio ID: {audio.id}\n"
        f"Script draft ID: {audio.script_draft_id}\n"
        f"Status: {audio.status}\n"
        f"Provider: {audio.provider}\n"
        f"Voice: {audio.voice}\n"
        f"Language: {audio.language}\n"
        f"File: {audio.file_path or 'None'}\n"
        f"Estimated duration: {audio.duration_seconds or 0:.2f}s\n"
        f"Subtitle timing lines: {len(audio.subtitle_timings)}\n"
        f"Scene timing suggestions: {len(audio.scene_timings)}\n"
        f"Error: {audio.error_message or 'None'}"
    )


def format_asset_plan(plan: AssetPlan) -> str:
    media_lines = "\n".join(
        f"  - beat {item.beat_index}: {item.provider} {item.media_type} "
        f"{item.width or '?'}x{item.height or '?'} | {item.source_url}"
        for item in plan.media_assets[:10]
    ) or "  - None"
    return (
        "RaatVerse asset plan prepared\n"
        f"Asset plan ID: {plan.id}\n"
        f"Script draft ID: {plan.script_draft_id}\n"
        f"Audio asset ID: {plan.audio_asset_id}\n"
        f"Status: {plan.status}\n"
        f"Media provider: {plan.provider}\n"
        f"Media candidates: {len(plan.media_assets)}\n"
        f"Subtitle timing lines: {len(plan.subtitle_timings)}\n"
        f"Scene timing suggestions: {len(plan.scene_timings)}\n"
        "Media summary:\n"
        f"{media_lines}\n"
        f"Error: {plan.error_message or 'None'}\n"
        "Next action: review assets before Phase 4 rendering."
    )
