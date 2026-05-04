from __future__ import annotations

import re

from raatverse_agent.config import Settings
from raatverse_agent.script_generation.models import ScriptDraft, ScriptValidationResult
from raatverse_agent.script_generation.prompts import normalize_category, supported_prompt_categories

BANNED_PHRASES = (
    "based on a true story",
    "real true story",
    "true incident",
    "sachchi ghatna",
    "sachi ghatna",
    "sachchi kahani",
    "yeh sach hai",
    "explicit sex",
    "graphic gore",
    "gore-heavy",
    "copied from",
)

HINGLISH_MARKERS = {
    "raat",
    "kahani",
    "ek",
    "tha",
    "thi",
    "hai",
    "nahi",
    "andar",
    "darwaza",
    "awaaz",
    "kal",
    "mat",
    "kyun",
    "jab",
}


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _word_count(value: str) -> int:
    return len(re.findall(r"[\w']+", value))


def validate_script_draft(settings: Settings, draft: ScriptDraft) -> ScriptValidationResult:
    issues: list[str] = []
    warnings: list[str] = []
    script = draft.narration_script.strip()
    script_normalized = _normalize_text(script)
    hook_normalized = _normalize_text(draft.hook)

    if not script:
        issues.append("Narration script is empty.")

    if draft.estimated_duration_seconds < settings.min_video_seconds:
        issues.append(
            f"Estimated duration {draft.estimated_duration_seconds}s is below minimum {settings.min_video_seconds}s."
        )
    if draft.estimated_duration_seconds > settings.max_video_seconds:
        issues.append(
            f"Estimated duration {draft.estimated_duration_seconds}s is above maximum {settings.max_video_seconds}s."
        )

    word_count = _word_count(script)
    if word_count < settings.script_min_words:
        issues.append(f"Script is too short: {word_count} words, minimum {settings.script_min_words}.")
    if word_count > settings.script_max_words:
        issues.append(f"Script is too long: {word_count} words, maximum {settings.script_max_words}.")

    cta_normalized = _normalize_text(settings.outro_cta)
    if cta_normalized not in script_normalized:
        issues.append("Required RaatVerse CTA is missing from narration script.")
    if _normalize_text(draft.cta_line) != cta_normalized:
        issues.append("cta_line does not match configured RaatVerse CTA.")

    if len(draft.hook.strip()) < 20 or _word_count(draft.hook) < 5:
        issues.append("Hook is missing or too weak for the 0-3 second opening.")
    elif not any(marker in hook_normalized for marker in ("raat", "kaun", "kyun", "kya", "mat", "phone", "darwaza", "awaaz")):
        warnings.append("Hook may need a stronger curiosity or suspense trigger.")

    valid_categories = {
        normalize_category(category)
        for category in (*settings.script_categories, *supported_prompt_categories())
    }
    if normalize_category(draft.category) not in valid_categories:
        issues.append(f"Category '{draft.category}' is not configured or supported.")

    language = draft.language_style.lower()
    if "hindi" not in language and "hinglish" not in language:
        issues.append("Language style must be Hindi or Hinglish.")

    tokens = set(re.findall(r"[a-zA-Z]+", script_normalized))
    if not tokens.intersection(HINGLISH_MARKERS) and not re.search(r"[\u0900-\u097F]", script):
        warnings.append("Script may not read like natural Hindi/Hinglish storytelling.")

    for phrase in BANNED_PHRASES:
        if phrase in script_normalized:
            issues.append(f"Blocked safety phrase detected: {phrase}")

    if not draft.scene_beats:
        issues.append("At least one scene beat is required.")
    if not draft.subtitle_lines:
        warnings.append("Subtitle-friendly lines are missing.")

    return ScriptValidationResult(is_valid=not issues, issues=issues, warnings=warnings)
