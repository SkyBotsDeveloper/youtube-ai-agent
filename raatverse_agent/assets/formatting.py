from __future__ import annotations

from raatverse_agent.assets.models import AssetPlan, AssetQualityReport, AudioAsset


def format_audio_asset(audio: AudioAsset) -> str:
    quality = audio.tts_quality_metadata or {}
    warnings = "\n".join(f"  - {warning}" for warning in quality.get("warnings", [])) or "  - None"
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
        f"TTS input characters: {quality.get('input_characters', len(audio.tts_text or ''))}\n"
        f"TTS chunks sent: {quality.get('chunk_count', len(audio.tts_chunks))}\n"
        f"Subtitle timing lines: {len(audio.subtitle_timings)}\n"
        f"Scene timing suggestions: {len(audio.scene_timings)}\n"
        "TTS quality warnings:\n"
        f"{warnings}\n"
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


def format_asset_quality_report(report: AssetQualityReport) -> str:
    providers = "\n".join(
        f"  - {provider}: {count}"
        for provider, count in sorted(report.provider_distribution.items())
    ) or "  - None"
    repeated = "\n".join(f"  - {url}" for url in report.repeated_urls) or "  - None"
    weak = ", ".join(str(index) for index in report.weak_beats) or "None"
    recommendations = "\n".join(
        f"  - {item}" for item in report.recommendations
    ) or "  - None"
    alignment_lines = []
    for item in report.beat_alignments:
        warnings = "; ".join(item.warnings) if item.warnings else "ok"
        alignment_lines.append(
            f"  - beat {item.beat_index}: score={item.visual_relevance_score:.2f} "
            f"duration={item.duration_allocated:.2f}s cta={item.is_cta_outro} | "
            f"{item.narration_excerpt or 'No narration'} | "
            f"query={item.query_used or 'None'} | media={item.selected_media_url or 'None'} | {warnings}"
        )
    alignments = "\n".join(alignment_lines) or "  - None"
    return (
        "RaatVerse asset quality report\n"
        f"Asset plan ID: {report.asset_plan_id}\n"
        f"Total beats: {report.total_beats}\n"
        f"Total media assets: {report.total_media_assets}\n"
        f"Unique media URLs: {report.unique_media_urls}\n"
        f"Unique media ratio: {report.unique_media_ratio:.2f}\n"
        f"Vertical media count: {report.vertical_media_count}\n"
        f"Missing local files: {report.missing_local_files}\n"
        f"Weak beats: {weak}\n"
        "Provider distribution:\n"
        f"{providers}\n"
        "Repeated URLs:\n"
        f"{repeated}\n"
        "Beat alignment:\n"
        f"{alignments}\n"
        "Recommendations:\n"
        f"{recommendations}"
    )
