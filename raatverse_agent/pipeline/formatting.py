from __future__ import annotations

from raatverse_agent.pipeline.models import PipelineSummary


def format_pipeline_summary(summary: PipelineSummary) -> str:
    asset_lines = "\n".join(
        f"  - {asset.query} ({asset.duration_seconds}s, {asset.provider})"
        for asset in summary.visual_assets
    )
    return (
        "RaatVerse mock pipeline completed\n"
        f"Run ID: {summary.run_uid}\n"
        f"Status: {summary.status}\n"
        f"Category: {summary.category}\n"
        f"Title: {summary.title}\n"
        f"Duration: {summary.render.duration_seconds}s, {summary.render.resolution}, {summary.render.aspect_ratio}\n"
        f"Script excerpt: {summary.script_excerpt}...\n"
        "Visual references:\n"
        f"{asset_lines}\n"
        f"Voiceover: {summary.voiceover.provider} / {summary.voiceover.voice_name} / {summary.voiceover.language_code}\n"
        f"Render output: {summary.render.output_path}\n"
        f"YouTube: {summary.upload.provider}, privacy={summary.upload.privacy_status}, approval_required={summary.upload.approval_required}\n"
        f"Next action: {summary.next_action}"
    )
