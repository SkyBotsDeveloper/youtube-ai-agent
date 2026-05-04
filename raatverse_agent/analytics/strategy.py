from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher

from raatverse_agent.analytics.models import (
    AnalyticsSnapshot,
    CategoryScoreSummary,
    StrategyCategoryAllocation,
    StrategyRecommendation,
)
from raatverse_agent.config import Settings
from raatverse_agent.db.repositories import RaatVerseRepository


class StrategyLearningService:
    def __init__(self, *, settings: Settings, repository: RaatVerseRepository):
        self.settings = settings
        self.repository = repository

    def update_category_scores(self) -> list[CategoryScoreSummary]:
        snapshots = self.repository.list_ready_analytics_snapshots()
        grouped: dict[str, list[AnalyticsSnapshot]] = defaultdict(list)
        for snapshot in snapshots:
            if snapshot.category:
                grouped[snapshot.category].append(snapshot)

        updated: list[CategoryScoreSummary] = []
        for category in self.settings.script_categories:
            category_snapshots = grouped.get(category, [])
            if not category_snapshots:
                existing = next(
                    (
                        score
                        for score in self.repository.list_category_score_summaries()
                        if score.category == category
                    ),
                    None,
                )
                if existing:
                    updated.append(existing)
                continue
            summary = self._summarize_category(category, category_snapshots)
            updated.append(self.repository.upsert_category_score_summary(summary))
        return sorted(updated, key=lambda item: (-item.avg_performance_score, item.category))

    def recommend(self) -> StrategyRecommendation:
        scores = self.repository.list_category_score_summaries()
        categories = list(self.settings.script_categories)
        active = [
            score
            for score in scores
            if score.category in categories and score.total_videos > 0 and score.confidence > 0
        ]
        ranked = sorted(
            active,
            key=lambda score: (
                -score.avg_performance_score,
                -score.confidence,
                categories.index(score.category) if score.category in categories else 999,
            ),
        )

        if not ranked:
            distribution = [
                StrategyCategoryAllocation(
                    category=category,
                    recommended_count=1,
                    reason="No analytics signal yet; keep the category mix balanced.",
                )
                for category in categories[:7]
            ]
            return StrategyRecommendation(
                summary="No analytics snapshots are available yet. Keep a balanced RaatVerse category mix.",
                weekly_distribution=distribution,
                ranked_categories=scores,
                exploration_rate=self.settings.strategy_exploration_rate,
                exploitation_rate=self.settings.strategy_exploitation_rate,
                avoid_notes=self._avoid_notes(),
                next_category=categories[0] if categories else None,
                machine_plan={
                    "mode": "balanced",
                    "weekly_distribution": {item.category: item.recommended_count for item in distribution},
                },
            )

        distribution = self._weekly_distribution(ranked, categories)
        top = ranked[0]
        channel_average = _average(score.avg_performance_score for score in ranked) or top.avg_performance_score
        multiplier = top.avg_performance_score / channel_average if channel_average else 1.0
        summary = (
            f"{top.category.replace('_', ' ').title()} is performing "
            f"{multiplier:.1f}x the scored category average with "
            f"{top.avg_like_rate:.1%} like rate and confidence {top.confidence:.2f}."
        )
        return StrategyRecommendation(
            summary=summary,
            weekly_distribution=distribution,
            ranked_categories=ranked,
            exploration_rate=self.settings.strategy_exploration_rate,
            exploitation_rate=self.settings.strategy_exploitation_rate,
            avoid_notes=self._avoid_notes(),
            next_category=top.category,
            machine_plan={
                "mode": "analytics_weighted",
                "next_category": top.category,
                "weekly_distribution": {item.category: item.recommended_count for item in distribution},
                "ranked_categories": [score.model_dump(mode="json") for score in ranked],
            },
        )

    def categories(self) -> list[CategoryScoreSummary]:
        return self.repository.list_category_score_summaries()

    def _summarize_category(
        self,
        category: str,
        snapshots: list[AnalyticsSnapshot],
    ) -> CategoryScoreSummary:
        by_upload: dict[int, list[AnalyticsSnapshot]] = defaultdict(list)
        for snapshot in snapshots:
            by_upload[snapshot.youtube_upload_id].append(snapshot)
        latest_per_upload = [max(items, key=lambda item: item.snapshot_date) for items in by_upload.values()]
        video_scores = [self._video_score(items) for items in by_upload.values()]
        total_videos = len(by_upload)
        recent = sorted(snapshots, key=lambda item: item.snapshot_date)[-3:]
        overall_score = _average(video_scores)
        trend_score = _average(item.performance_score for item in recent) - overall_score
        story_type = _most_common([snapshot.story_type for snapshot in latest_per_upload if snapshot.story_type])
        confidence = min(
            1.0,
            _average(item.confidence for item in latest_per_upload) * min(1.0, max(total_videos, 1) / 5 + 0.2),
        )
        return CategoryScoreSummary(
            category=category,
            story_type=story_type,
            total_videos=total_videos,
            avg_views=_average(item.views for item in latest_per_upload),
            avg_likes=_average(item.likes for item in latest_per_upload),
            avg_comments=_average(item.comments for item in latest_per_upload),
            avg_like_rate=_average(item.like_rate for item in latest_per_upload),
            avg_comment_rate=_average(item.comment_rate for item in latest_per_upload),
            avg_average_view_duration=_average(item.average_view_duration for item in latest_per_upload),
            avg_subscribers_gained=_average(item.subscribers_gained for item in latest_per_upload),
            avg_performance_score=round(overall_score, 2),
            trend_score=round(trend_score, 2),
            confidence=round(confidence, 2),
        )

    def _video_score(self, snapshots: list[AnalyticsSnapshot]) -> float:
        early = _latest_window(snapshots, ("48h", "24h", "manual"))
        seven_day = _latest_window(snapshots, ("7d",))
        if early and seven_day:
            return (
                early.performance_score * self.settings.analytics_early_window_weight
                + seven_day.performance_score * self.settings.analytics_seven_day_weight
            )
        latest = max(snapshots, key=lambda item: item.snapshot_date)
        return latest.performance_score

    def _weekly_distribution(
        self,
        ranked: list[CategoryScoreSummary],
        categories: list[str],
    ) -> list[StrategyCategoryAllocation]:
        total_slots = 7
        exploitation_slots = max(1, min(total_slots, round(total_slots * self.settings.strategy_exploitation_rate)))
        exploration_slots = total_slots - exploitation_slots
        counts: dict[str, int] = defaultdict(int)

        top = ranked[0]
        counts[top.category] += max(1, min(4, exploitation_slots - 1 if len(ranked) > 1 else exploitation_slots))
        remaining_exploit = exploitation_slots - counts[top.category]
        for score in ranked[1:]:
            if remaining_exploit <= 0:
                break
            counts[score.category] += 1
            remaining_exploit -= 1
        while remaining_exploit > 0:
            counts[top.category] += 1
            remaining_exploit -= 1

        variety = [category for category in categories if category not in counts]
        variety.extend(score.category for score in reversed(ranked) if score.category not in variety)
        for category in variety[:exploration_slots]:
            counts[category] += 1

        score_by_category = {score.category: score for score in ranked}
        allocations: list[StrategyCategoryAllocation] = []
        for category, count in sorted(counts.items(), key=lambda item: (-item[1], categories.index(item[0]) if item[0] in categories else 999)):
            score = score_by_category.get(category)
            if score:
                reason = (
                    f"Analytics-backed category with score {score.avg_performance_score:.1f} "
                    f"and confidence {score.confidence:.2f}."
                )
                allocations.append(
                    StrategyCategoryAllocation(
                        category=category,
                        recommended_count=count,
                        reason=reason,
                        avg_performance_score=score.avg_performance_score,
                        confidence=score.confidence,
                    )
                )
            else:
                allocations.append(
                    StrategyCategoryAllocation(
                        category=category,
                        recommended_count=count,
                        reason="Exploration slot for variety and fresh story patterns.",
                    )
                )
        return allocations

    def _avoid_notes(self) -> list[str]:
        drafts = self.repository.list_script_drafts(limit=8)
        hooks = [draft.hook for draft in drafts if draft.hook]
        for index, hook in enumerate(hooks):
            for other in hooks[index + 1 :]:
                if SequenceMatcher(None, hook.lower(), other.lower()).ratio() >= 0.78:
                    return ["Avoid repeating recent hook patterns; recent hook similarity is high."]
        return ["Keep hooks distinct from recent approved drafts and avoid repeated phone-message reveals."]


def _average(values) -> float:
    items = [float(value) for value in values]
    if not items:
        return 0.0
    return sum(items) / len(items)


def _latest_window(
    snapshots: list[AnalyticsSnapshot],
    windows: tuple[str, ...],
) -> AnalyticsSnapshot | None:
    candidates = [snapshot for snapshot in snapshots if snapshot.snapshot_window in windows]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.snapshot_date)


def _most_common(values: list[str]) -> str | None:
    if not values:
        return None
    return max(sorted(set(values)), key=values.count)
