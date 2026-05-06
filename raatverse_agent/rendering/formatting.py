from __future__ import annotations

from raatverse_agent.rendering.models import RenderValidationResult, VideoRender


def format_video_render(render: VideoRender) -> str:
    timing = render.timing_report or {}
    timing_warnings = "\n".join(f"  - {item}" for item in timing.get("warnings", [])) or "  - None"
    return (
        "RaatVerse render completed\n"
        f"Render ID: {render.id}\n"
        f"Asset plan ID: {render.asset_plan_id}\n"
        f"Script draft ID: {render.script_draft_id}\n"
        f"Status: {render.status}\n"
        f"Provider: {render.renderer_provider}\n"
        f"Output: {render.output_path or 'None'}\n"
        f"Preview: {render.preview_path or 'None'}\n"
        f"Duration: {render.duration_seconds or 0:.2f}s\n"
        f"Resolution: {render.resolution}\n"
        f"FPS: {render.fps}\n"
        "Timing report:\n"
        f"  - Actual audio duration: {float(timing.get('actual_audio_duration_seconds') or 0):.2f}s\n"
        f"  - Final video duration: {float(timing.get('final_video_duration_seconds') or render.duration_seconds or 0):.2f}s\n"
        f"  - CTA duration: {float(timing.get('cta_duration_seconds') or 0):.2f}s\n"
        f"  - Shortest scene beat: {float(timing.get('shortest_scene_beat_duration_seconds') or 0):.2f}s\n"
        f"  - Subtitle count: {int(timing.get('subtitle_count') or 0)}\n"
        f"  - Subtitle timing mode used: {timing.get('subtitle_timing_mode_used') or 'unknown'}\n"
        f"  - Boundary-aligned subtitle lines: {int(timing.get('subtitle_boundary_aligned_lines') or 0)}\n"
        f"  - Fallback-aligned subtitle lines: {int(timing.get('subtitle_fallback_aligned_lines') or 0)}\n"
        f"  - Earliest subtitle start delta: {float(timing.get('subtitle_earliest_start_delta_seconds') or 0):.2f}s\n"
        f"  - Latest subtitle start delta: {float(timing.get('subtitle_latest_start_delta_seconds') or 0):.2f}s\n"
        f"  - Subtitle offset used: {float(timing.get('subtitle_global_offset_seconds') or 0):.2f}s\n"
        f"  - Subtitle end padding: {float(timing.get('subtitle_end_padding_seconds') or 0):.2f}s\n"
        f"  - Timing scaled to audio: {bool(timing.get('timing_scaled_to_audio'))}\n"
        f"  - Subtitle timing source: {timing.get('subtitle_timing_source') or 'unknown'}\n"
        f"  - CTA TTS mode: {timing.get('cta_tts_mode') or 'unknown'}\n"
        f"  - CTA TTS override used: {bool(timing.get('cta_tts_override_used'))}\n"
        f"  - CTA outro screen enabled: {bool(timing.get('cta_outro_screen_enabled'))}\n"
        f"  - CTA subscribe button enabled: {bool(timing.get('cta_subscribe_button_enabled'))}\n"
        "Timing warnings:\n"
        f"{timing_warnings}\n"
        f"Command summary: {render.ffmpeg_command_summary or 'None'}\n"
        f"Error: {render.error_message or 'None'}"
    )


def format_render_validation(result: RenderValidationResult) -> str:
    issues = "\n".join(f"  - {issue}" for issue in result.issues) or "  - None"
    warnings = "\n".join(f"  - {warning}" for warning in result.warnings) or "  - None"
    return (
        "RaatVerse render validation\n"
        f"Valid: {result.is_valid}\n"
        "Issues:\n"
        f"{issues}\n"
        "Warnings:\n"
        f"{warnings}"
    )
