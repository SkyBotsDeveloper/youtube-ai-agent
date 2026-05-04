from __future__ import annotations

from raatverse_agent.analytics.models import (
    AnalyticsSnapshot,
    CategoryScoreSummary,
    DueSnapshotCandidate,
    StrategyRecommendation,
)


def format_analytics_snapshot(snapshot: AnalyticsSnapshot) -> str:
    return (
        "RaatVerse analytics snapshot\n"
        f"Snapshot ID: {snapshot.id}\n"
        f"Upload ID: {snapshot.youtube_upload_id}\n"
        f"YouTube video ID: {snapshot.youtube_video_id}\n"
        f"Window: {snapshot.snapshot_window}\n"
        f"Status: {snapshot.status}\n"
        f"Provider: {snapshot.provider}\n"
        f"Category: {snapshot.category}/{snapshot.story_type}\n"
        f"Days since upload: {snapshot.days_since_upload}\n"
        f"Views: {snapshot.views}\n"
        f"Likes: {snapshot.likes} ({snapshot.like_rate:.2%})\n"
        f"Comments: {snapshot.comments} ({snapshot.comment_rate:.2%})\n"
        f"Shares: {snapshot.shares}\n"
        f"Average view duration: {snapshot.average_view_duration:.2f}s\n"
        f"Estimated minutes watched: {snapshot.estimated_minutes_watched:.2f}\n"
        f"Subscribers gained/lost: {snapshot.subscribers_gained}/{snapshot.subscribers_lost}\n"
        f"Performance score: {snapshot.performance_score:.2f}\n"
        f"Confidence: {snapshot.confidence:.2f}\n"
        f"Error: {snapshot.error_message or 'None'}"
    )


def format_category_score(score: CategoryScoreSummary) -> str:
    return (
        f"{score.category}: videos={score.total_videos} "
        f"score={score.avg_performance_score:.2f} confidence={score.confidence:.2f} "
        f"avg_views={score.avg_views:.1f} like_rate={score.avg_like_rate:.2%} "
        f"trend={score.trend_score:.2f}"
    )


def format_strategy_recommendation(recommendation: StrategyRecommendation) -> str:
    lines = [
        "RaatVerse strategy recommendation",
        f"Summary: {recommendation.summary}",
        f"Next category: {recommendation.next_category or 'None'}",
        (
            "Exploration/exploitation: "
            f"{recommendation.exploration_rate:.0%}/{recommendation.exploitation_rate:.0%}"
        ),
        "Weekly distribution:",
    ]
    lines.extend(
        f"  - {item.category}: {item.recommended_count} | {item.reason}"
        for item in recommendation.weekly_distribution
    )
    if recommendation.avoid_notes:
        lines.append("Avoid notes:")
        lines.extend(f"  - {note}" for note in recommendation.avoid_notes)
    return "\n".join(lines)


def format_due_snapshots(candidates: list[DueSnapshotCandidate]) -> str:
    if not candidates:
        return "No analytics snapshots are due."
    lines = ["RaatVerse analytics snapshots due"]
    for candidate in candidates:
        windows = ", ".join(candidate.due_windows)
        lines.append(
            f"{candidate.youtube_upload_id}: video={candidate.youtube_video_id} "
            f"days={candidate.days_since_upload:.2f} windows={windows} title={candidate.title}"
        )
    return "\n".join(lines)
