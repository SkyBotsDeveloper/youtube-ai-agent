from __future__ import annotations

from raatverse_agent.script_generation.models import ScriptDraft, ScriptGenerationResponse


def format_script_generation_response(response: ScriptGenerationResponse) -> str:
    if response.draft is None:
        return f"Script generation failed\nProvider: {response.provider}\nError: {response.error}"

    draft = response.draft
    warnings = "\n".join(f"  - {warning}" for warning in response.validation.warnings) or "  - None"
    issues = "\n".join(f"  - {issue}" for issue in response.validation.issues) or "  - None"
    beats = "\n".join(
        f"  - {beat.start_second}-{beat.end_second}s: {beat.visual_suggestion}"
        for beat in draft.scene_beats[:5]
    )
    return (
        "RaatVerse script draft generated\n"
        f"Draft ID: {response.saved_draft_id}\n"
        f"Status: {draft.status}\n"
        f"Provider: {response.provider}\n"
        f"Title: {draft.title}\n"
        f"Category: {draft.category}\n"
        f"Story type: {draft.story_type}\n"
        f"Duration: {draft.estimated_duration_seconds}s\n"
        f"Hook: {draft.hook}\n"
        f"Script excerpt: {draft.narration_script[:360]}...\n"
        "Scene beats:\n"
        f"{beats}\n"
        "Validation issues:\n"
        f"{issues}\n"
        "Validation warnings:\n"
        f"{warnings}\n"
        "Next action: review the draft, then approve or reject it."
    )


def format_script_draft(draft: ScriptDraft) -> str:
    beats = "\n".join(
        f"  - {beat.start_second}-{beat.end_second}s: {beat.narration} | {beat.visual_suggestion}"
        for beat in draft.scene_beats
    )
    subtitles = "\n".join(f"  - {line}" for line in draft.subtitle_lines)
    return (
        f"Draft ID: {draft.id}\n"
        f"UID: {draft.draft_uid}\n"
        f"Status: {draft.status}\n"
        f"Provider: {draft.provider}\n"
        f"Title: {draft.title}\n"
        f"Category: {draft.category}\n"
        f"Story type: {draft.story_type}\n"
        f"Duration: {draft.estimated_duration_seconds}s\n"
        f"Language: {draft.language_style}\n"
        f"Hook: {draft.hook}\n"
        f"CTA: {draft.cta_line}\n"
        "Narration:\n"
        f"{draft.narration_script}\n"
        "Scene beats:\n"
        f"{beats}\n"
        "Subtitle lines:\n"
        f"{subtitles}\n"
        f"Rejection/revision reason: {draft.rejection_reason or 'None'}"
    )
