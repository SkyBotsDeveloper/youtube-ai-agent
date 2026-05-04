from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from raatverse_agent.assets.models import AssetPlan, AssetQualityReport, MediaAssetCandidate
from raatverse_agent.config import Settings


def is_vertical_media(candidate: MediaAssetCandidate) -> bool:
    if candidate.width is None or candidate.height is None:
        return False
    return candidate.height >= candidate.width


def select_diverse_media_candidates(
    candidates: list[MediaAssetCandidate],
    *,
    beat_count: int,
    settings: Settings,
) -> list[MediaAssetCandidate]:
    """Choose one render-ready candidate per beat while avoiding repeated source URLs."""

    by_beat: dict[int, list[MediaAssetCandidate]] = defaultdict(list)
    for candidate in candidates:
        by_beat[candidate.beat_index].append(candidate)

    selected: list[MediaAssetCandidate] = []
    usage: Counter[str] = Counter()
    for beat_index in range(beat_count):
        beat_candidates = sorted(
            by_beat.get(beat_index, []),
            key=lambda item: _candidate_rank(item, settings, usage[item.source_url]),
            reverse=True,
        )
        choice = _choose_candidate(beat_candidates, settings, usage)
        if choice is None:
            choice = _placeholder_candidate(beat_index)
        usage[choice.source_url] += 1
        selected.append(choice)
    return selected


def analyze_asset_plan(plan: AssetPlan, settings: Settings) -> AssetQualityReport:
    urls = [item.source_url for item in plan.media_assets if item.source_url]
    url_counts = Counter(urls)
    repeated = sorted(url for url, count in url_counts.items() if count > 1)
    provider_counts = Counter(item.provider for item in plan.media_assets)
    vertical_count = sum(1 for item in plan.media_assets if is_vertical_media(item))
    missing_local = sum(
        1
        for item in plan.media_assets
        if item.local_file_path and not Path(item.local_file_path).exists()
    )
    total_beats = len(plan.scene_timings) or max((item.beat_index for item in plan.media_assets), default=-1) + 1
    unique_ratio = len(set(urls)) / max(1, total_beats)
    weak_beats = _weak_beats(plan, settings)
    recommendations = _recommendations(
        total_beats=total_beats,
        unique_ratio=unique_ratio,
        repeated=repeated,
        vertical_count=vertical_count,
        missing_local=missing_local,
        weak_beats=weak_beats,
        settings=settings,
    )
    return AssetQualityReport(
        asset_plan_id=plan.id,
        total_beats=total_beats,
        total_media_assets=len(plan.media_assets),
        unique_media_urls=len(set(urls)),
        repeated_urls=repeated,
        vertical_media_count=vertical_count,
        missing_local_files=missing_local,
        provider_distribution=dict(provider_counts),
        weak_beats=weak_beats,
        unique_media_ratio=round(unique_ratio, 3),
        recommendations=recommendations,
    )


def _candidate_rank(candidate: MediaAssetCandidate, settings: Settings, reuse_count: int) -> tuple:
    duplicate_allowed = reuse_count < settings.stock_media_max_reuse_per_url
    vertical = is_vertical_media(candidate)
    media_type_score = 1 if candidate.media_type.lower() == "video" else 0
    resolution_score = _resolution_score(candidate)
    duplicate_score = 1 if duplicate_allowed or not settings.stock_media_avoid_duplicates else 0
    vertical_score = 1 if vertical or not settings.stock_media_prefer_vertical else 0
    return (
        duplicate_score,
        vertical_score,
        media_type_score,
        resolution_score,
        candidate.score,
    )


def _choose_candidate(
    candidates: list[MediaAssetCandidate],
    settings: Settings,
    usage: Counter[str],
) -> MediaAssetCandidate | None:
    if not candidates:
        return None
    if not settings.stock_media_avoid_duplicates:
        return _with_quality_score(candidates[0], settings, usage[candidates[0].source_url])
    for candidate in candidates:
        if usage[candidate.source_url] < settings.stock_media_max_reuse_per_url:
            return _with_quality_score(candidate, settings, usage[candidate.source_url])
    return _with_quality_score(candidates[0], settings, usage[candidates[0].source_url])


def _with_quality_score(
    candidate: MediaAssetCandidate,
    settings: Settings,
    reuse_count: int,
) -> MediaAssetCandidate:
    rank = _candidate_rank(candidate, settings, reuse_count)
    score = round(candidate.score + (rank[1] * 0.25) + (rank[2] * 0.1) + (rank[3] * 0.2), 3)
    if settings.stock_media_avoid_duplicates and reuse_count >= settings.stock_media_max_reuse_per_url:
        score -= 0.5
    return candidate.model_copy(update={"score": score})


def _resolution_score(candidate: MediaAssetCandidate) -> float:
    if not candidate.width or not candidate.height:
        return 0.0
    target_ratio = 1080 / 1920
    ratio = candidate.width / max(1, candidate.height)
    ratio_score = max(0.0, 1.0 - abs(target_ratio - ratio))
    height_score = min(1.0, candidate.height / 1920)
    return round((ratio_score + height_score) / 2, 3)


def _placeholder_candidate(beat_index: int) -> MediaAssetCandidate:
    return MediaAssetCandidate(
        provider="placeholder",
        query="dark cinematic vertical placeholder background",
        media_type="video",
        source_url=f"placeholder://raatverse/beat-{beat_index}",
        creator_name="RaatVerse generated placeholder",
        license_note="Local generated dark background placeholder; no stock source.",
        width=1080,
        height=1920,
        duration_seconds=None,
        beat_index=beat_index,
        score=0.2,
    )


def _weak_beats(plan: AssetPlan, settings: Settings) -> list[int]:
    weak: list[int] = []
    by_beat: dict[int, list[MediaAssetCandidate]] = defaultdict(list)
    for item in plan.media_assets:
        by_beat[item.beat_index].append(item)
    total_beats = len(plan.scene_timings) or max((item.beat_index for item in plan.media_assets), default=-1) + 1
    for beat_index in range(total_beats):
        items = by_beat.get(beat_index, [])
        if not items:
            weak.append(beat_index)
            continue
        best = max(items, key=lambda item: item.score)
        if best.provider == "placeholder":
            weak.append(beat_index)
            continue
        if settings.stock_media_prefer_vertical and not any(is_vertical_media(item) for item in items):
            weak.append(beat_index)
    return weak


def _recommendations(
    *,
    total_beats: int,
    unique_ratio: float,
    repeated: list[str],
    vertical_count: int,
    missing_local: int,
    weak_beats: list[int],
    settings: Settings,
) -> list[str]:
    recommendations: list[str] = []
    if repeated:
        recommendations.append("Repeated stock URLs detected; regenerate assets or use STOCK_MEDIA_PROVIDER=both.")
    if unique_ratio < 0.70:
        recommendations.append("Less than 70% of beats have unique media; refine scene stock_search_query values.")
    if total_beats >= settings.stock_media_min_unique_per_plan and unique_ratio < 1.0:
        recommendations.append(
            f"Plan target is at least {settings.stock_media_min_unique_per_plan} unique media URLs; rerun with more specific queries."
        )
    if vertical_count < max(1, round(total_beats * 0.70)) and settings.stock_media_prefer_vertical:
        recommendations.append("Too few vertical assets; prefer portrait stock clips or add vertical-specific queries.")
    if missing_local:
        recommendations.append("Some selected media local files are missing; rerun assets prepare with --download.")
    if weak_beats:
        recommendations.append(f"Weak beats need better visual matches: {', '.join(map(str, weak_beats))}.")
    if not recommendations:
        recommendations.append("Asset plan has acceptable diversity for a first render pass.")
    return recommendations
