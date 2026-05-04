from __future__ import annotations

from raatverse_agent.rendering.models import RenderValidationResult, VideoRender


def format_video_render(render: VideoRender) -> str:
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
