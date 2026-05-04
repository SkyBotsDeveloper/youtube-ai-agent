from __future__ import annotations

from collections.abc import Sequence

from raatverse_agent.analytics.models import AnalyticsSnapshot
from raatverse_agent.config import Settings


def enrich_snapshot_scores(
    settings: Settings,
    snapshot: AnalyticsSnapshot,
    previous_snapshots: Sequence[AnalyticsSnapshot],
    *,
    category_video_count: int = 0,
) -> AnalyticsSnapshot:
    views = max(snapshot.views, 0)
    like_rate = _rate(snapshot.likes, views)
    comment_rate = _rate(snapshot.comments, views)
    subscriber_gain_rate = _rate(snapshot.subscribers_gained, views)

    baselines = _channel_baselines(previous_snapshots, fallback=snapshot)
    retention_score = _retention_score(snapshot.average_view_duration, settings.target_duration_seconds)
    performance_score = _weighted_score(
        settings,
        views_score=_ratio_score(views, baselines["views"]),
        like_score=_ratio_score(like_rate, baselines["like_rate"]),
        comment_score=_ratio_score(comment_rate, baselines["comment_rate"]),
        retention_score=retention_score,
        subscriber_score=_ratio_score(snapshot.subscribers_gained, baselines["subscribers_gained"]),
    )
    confidence = _confidence(snapshot, category_video_count)

    return snapshot.model_copy(
        update={
            "like_rate": like_rate,
            "comment_rate": comment_rate,
            "subscriber_gain_rate": subscriber_gain_rate,
            "retention_score": round(retention_score, 2),
            "performance_score": round(performance_score, 2),
            "confidence": round(confidence, 2),
        }
    )


def _rate(numerator: int | float, denominator: int | float) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def _channel_baselines(
    snapshots: Sequence[AnalyticsSnapshot],
    *,
    fallback: AnalyticsSnapshot,
) -> dict[str, float]:
    ready = [snapshot for snapshot in snapshots if snapshot.status == "snapshot_ready"]
    if not ready:
        return {
            "views": max(float(fallback.views), 1.0),
            "like_rate": max(_rate(fallback.likes, fallback.views), 0.01),
            "comment_rate": max(_rate(fallback.comments, fallback.views), 0.002),
            "subscribers_gained": max(float(fallback.subscribers_gained), 1.0),
        }

    return {
        "views": max(_avg(snapshot.views for snapshot in ready), 1.0),
        "like_rate": max(_avg(snapshot.like_rate or _rate(snapshot.likes, snapshot.views) for snapshot in ready), 0.01),
        "comment_rate": max(
            _avg(snapshot.comment_rate or _rate(snapshot.comments, snapshot.views) for snapshot in ready),
            0.002,
        ),
        "subscribers_gained": max(_avg(snapshot.subscribers_gained for snapshot in ready), 1.0),
    }


def _avg(values) -> float:
    items = [float(value) for value in values]
    if not items:
        return 0.0
    return sum(items) / len(items)


def _ratio_score(value: float, baseline: float) -> float:
    if baseline <= 0:
        return 50.0 if value > 0 else 0.0
    ratio = max(0.0, min(value / baseline, 3.0))
    # Ratio 1.0 means channel-average performance. 3.0x is capped at 100.
    return max(0.0, min(100.0, 50.0 + ((ratio - 1.0) * 25.0)))


def _retention_score(average_view_duration: float, target_duration: int) -> float:
    if target_duration <= 0:
        return 0.0
    ratio = max(0.0, min(float(average_view_duration) / float(target_duration), 1.0))
    return ratio * 100.0


def _weighted_score(
    settings: Settings,
    *,
    views_score: float,
    like_score: float,
    comment_score: float,
    retention_score: float,
    subscriber_score: float,
) -> float:
    weights = {
        "views": settings.analytics_weight_views,
        "like": settings.analytics_weight_like_rate,
        "comment": settings.analytics_weight_comment_rate,
        "retention": settings.analytics_weight_retention,
        "subscriber": settings.analytics_weight_subscribers,
    }
    total_weight = sum(weights.values()) or 1.0
    return (
        (views_score * weights["views"])
        + (like_score * weights["like"])
        + (comment_score * weights["comment"])
        + (retention_score * weights["retention"])
        + (subscriber_score * weights["subscriber"])
    ) / total_weight


def _confidence(snapshot: AnalyticsSnapshot, category_video_count: int) -> float:
    window_factor = {
        "manual": 0.35,
        "24h": 0.55,
        "48h": 0.75,
        "7d": 0.95,
    }.get(snapshot.snapshot_window, 0.35)
    available_metrics = sum(
        1
        for value in (
            snapshot.views,
            snapshot.likes,
            snapshot.comments,
            snapshot.estimated_minutes_watched,
            snapshot.average_view_duration,
            snapshot.subscribers_gained,
        )
        if value > 0
    )
    metric_factor = available_metrics / 6
    sample_factor = min(max(category_video_count, 0) / 5, 1.0)
    return max(0.1, min(1.0, (0.5 * window_factor) + (0.3 * metric_factor) + (0.2 * sample_factor)))
