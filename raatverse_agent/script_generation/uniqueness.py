from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable

from raatverse_agent.config import Settings
from raatverse_agent.script_generation.models import ScriptDraft, ScriptValidationResult
from raatverse_agent.script_generation.prompts import normalize_category


def normalize_for_similarity(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9\u0900-\u097F\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def similarity(left: str, right: str) -> float:
    left_normalized = normalize_for_similarity(left)
    right_normalized = normalize_for_similarity(right)
    if not left_normalized or not right_normalized:
        return 0.0
    return SequenceMatcher(None, left_normalized, right_normalized).ratio()


def ngram_overlap(left: str, right: str, n: int = 4) -> float:
    def grams(text: str) -> set[tuple[str, ...]]:
        words = normalize_for_similarity(text).split()
        return {
            tuple(words[index : index + n])
            for index in range(0, max(len(words) - n + 1, 0))
        }

    left_grams = grams(left)
    right_grams = grams(right)
    if not left_grams or not right_grams:
        return 0.0
    return len(left_grams.intersection(right_grams)) / len(left_grams.union(right_grams))


class UniquenessChecker:
    def __init__(self, settings: Settings):
        self.settings = settings

    def evaluate(self, draft: ScriptDraft, existing_items: Iterable[dict]) -> ScriptValidationResult:
        issues: list[str] = []
        warnings: list[str] = []
        recent_same_pair = 0

        for item in existing_items:
            title = str(item.get("title") or "")
            hook = str(item.get("hook") or "")
            script = str(item.get("script_text") or item.get("narration_script") or "")
            category = normalize_category(str(item.get("category") or ""))
            story_type = normalize_category(str(item.get("story_type") or ""))

            title_similarity = similarity(draft.title, title)
            if title_similarity >= self.settings.script_similarity_threshold:
                issues.append(
                    f"Title is too similar to existing draft/video '{title}' ({title_similarity:.2f})."
                )

            hook_similarity = similarity(draft.hook, hook)
            if hook_similarity >= self.settings.script_similarity_threshold:
                issues.append(
                    f"Hook is too similar to an existing hook ({hook_similarity:.2f})."
                )

            script_similarity = max(
                similarity(draft.narration_script, script),
                ngram_overlap(draft.narration_script, script),
            )
            if script_similarity >= self.settings.script_similarity_threshold:
                issues.append(
                    f"Narration appears repetitive compared with existing content ({script_similarity:.2f})."
                )

            if (
                category == normalize_category(draft.category)
                and story_type == normalize_category(draft.story_type)
            ):
                recent_same_pair += 1

        if recent_same_pair >= self.settings.script_max_recent_same_category_story_type:
            warnings.append(
                "Same category/story_type has been used often recently; consider regenerating for variety."
            )

        return ScriptValidationResult(is_valid=not issues, issues=issues, warnings=warnings)
