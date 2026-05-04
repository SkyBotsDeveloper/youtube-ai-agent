from __future__ import annotations

from collections.abc import Sequence

from raatverse_agent.config import Settings
from raatverse_agent.pipeline.models import CategoryScoreState
from raatverse_agent.script_generation.prompts import normalize_category


class ScriptCategoryStrategy:
    """Analytics-aware placeholder for category selection.

    It is deterministic in Phase 2 so tests and scheduled jobs remain predictable.
    The exploitation/exploration split is represented in prompt preferences and
    ranking, not by random behavior.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def ranked_categories(
        self,
        categories: Sequence[str],
        category_scores: Sequence[CategoryScoreState],
    ) -> list[str]:
        if not categories:
            return []

        scores = {normalize_category(score.category): score for score in category_scores}
        normalized_categories = [normalize_category(category) for category in categories]
        any_signal = any(score.uploads > 0 or score.views > 0 or score.likes > 0 for score in scores.values())

        if not any_signal:
            return normalized_categories

        winning_count = max(1, round(len(normalized_categories) * self.settings.script_exploitation_rate))
        ranked_by_score = sorted(
            normalized_categories,
            key=lambda category: (
                -(scores.get(category).score if scores.get(category) else 0.0),
                scores.get(category).uploads if scores.get(category) else 0,
                normalized_categories.index(category),
            ),
        )
        winners = ranked_by_score[:winning_count]
        variety = [
            category
            for category in sorted(
                normalized_categories,
                key=lambda category: (
                    scores.get(category).uploads if scores.get(category) else 0,
                    normalized_categories.index(category),
                ),
            )
            if category not in winners
        ]
        return [*winners, *variety]

    def choose_category(
        self,
        categories: Sequence[str],
        category_scores: Sequence[CategoryScoreState],
    ) -> str:
        ranked = self.ranked_categories(categories, category_scores)
        if not ranked:
            raise ValueError("At least one script category is required.")
        return ranked[0]
