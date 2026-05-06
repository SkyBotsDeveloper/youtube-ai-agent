from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

from raatverse_agent.assets.models import AssetBeatAlignment, AssetPlan, AssetQualityReport, MediaAssetCandidate
from raatverse_agent.assets.timing import is_cta_scene
from raatverse_agent.config import Settings
from raatverse_agent.script_generation.models import ScriptDraft, ScriptSceneBeat


def is_vertical_media(candidate: MediaAssetCandidate) -> bool:
    if candidate.width is None or candidate.height is None:
        return False
    return candidate.height >= candidate.width


def select_diverse_media_candidates(
    candidates: list[MediaAssetCandidate],
    *,
    beat_count: int,
    settings: Settings,
    draft: ScriptDraft | None = None,
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
            key=lambda item: _candidate_rank(item, settings, usage[item.source_url], _beat_for_index(draft, beat_index)),
            reverse=True,
        )
        choice = _choose_candidate(beat_candidates, settings, usage, _beat_for_index(draft, beat_index))
        if choice is None:
            choice = _placeholder_candidate(beat_index)
        usage[choice.source_url] += 1
        selected.append(choice)
    return selected


def analyze_asset_plan(
    plan: AssetPlan,
    settings: Settings,
    draft: ScriptDraft | None = None,
) -> AssetQualityReport:
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
    beat_alignments = _beat_alignments(plan, settings, draft)
    weak_beats = sorted(
        {
            *(_weak_beats(plan, settings)),
            *(item.beat_index for item in beat_alignments if item.visual_relevance_score < settings.visual_relevance_min_score),
        }
    )
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
        beat_alignments=beat_alignments,
        recommendations=recommendations,
    )


def score_visual_relevance(
    candidate: MediaAssetCandidate,
    settings: Settings,
    beat: ScriptSceneBeat | None = None,
    *,
    reuse_count: int = 0,
) -> float:
    vertical_score = 1.0 if is_vertical_media(candidate) or not settings.stock_media_prefer_vertical else 0.0
    resolution_score = _resolution_score(candidate)
    query_match = _query_match_score(candidate, beat)
    location_score = _metadata_match_score(candidate, beat.location if beat else None) if settings.visual_relevance_prefer_location else 0.0
    mood_score = _metadata_match_score(candidate, beat.mood if beat else None) if settings.visual_relevance_prefer_mood else 0.0
    action_source = " ".join(
        item
        for item in [
            beat.narration if beat else "",
            beat.narration_segment if beat and beat.narration_segment else "",
            beat.camera_motion if beat and beat.camera_motion else "",
        ]
        if item
    )
    action_score = _metadata_match_score(candidate, action_source) if settings.visual_relevance_prefer_action else 0.0
    uniqueness_score = 1.0 if reuse_count < settings.stock_media_max_reuse_per_url else 0.0
    provider_score = 1.0 if candidate.provider != "placeholder" else 0.2
    score = (
        vertical_score * 0.22
        + resolution_score * 0.16
        + query_match * 0.22
        + location_score * 0.10
        + mood_score * 0.10
        + action_score * 0.10
        + uniqueness_score * 0.06
        + provider_score * 0.04
    )
    return round(max(0.0, min(1.0, score)), 3)


def _candidate_rank(
    candidate: MediaAssetCandidate,
    settings: Settings,
    reuse_count: int,
    beat: ScriptSceneBeat | None,
) -> tuple:
    duplicate_allowed = reuse_count < settings.stock_media_max_reuse_per_url
    vertical = is_vertical_media(candidate)
    media_type_score = 1 if candidate.media_type.lower() == "video" else 0
    resolution_score = _resolution_score(candidate)
    duplicate_score = 1 if duplicate_allowed or not settings.stock_media_avoid_duplicates else 0
    vertical_score = 1 if vertical or not settings.stock_media_prefer_vertical else 0
    relevance_score = score_visual_relevance(candidate, settings, beat, reuse_count=reuse_count)
    return (
        duplicate_score,
        relevance_score,
        vertical_score,
        media_type_score,
        resolution_score,
        candidate.score,
    )


def _choose_candidate(
    candidates: list[MediaAssetCandidate],
    settings: Settings,
    usage: Counter[str],
    beat: ScriptSceneBeat | None,
) -> MediaAssetCandidate | None:
    if not candidates:
        return None
    if not settings.stock_media_avoid_duplicates:
        return _with_quality_score(candidates[0], settings, usage[candidates[0].source_url], beat)
    for candidate in candidates:
        if usage[candidate.source_url] < settings.stock_media_max_reuse_per_url:
            return _with_quality_score(candidate, settings, usage[candidate.source_url], beat)
    return _with_quality_score(candidates[0], settings, usage[candidates[0].source_url], beat)


def _with_quality_score(
    candidate: MediaAssetCandidate,
    settings: Settings,
    reuse_count: int,
    beat: ScriptSceneBeat | None,
) -> MediaAssetCandidate:
    score = score_visual_relevance(candidate, settings, beat, reuse_count=reuse_count)
    if settings.stock_media_avoid_duplicates and reuse_count >= settings.stock_media_max_reuse_per_url:
        score = max(0.0, score - 0.25)
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


def _beat_alignments(
    plan: AssetPlan,
    settings: Settings,
    draft: ScriptDraft | None,
) -> list[AssetBeatAlignment]:
    alignments: list[AssetBeatAlignment] = []
    for scene in plan.scene_timings:
        media = _selected_media_for_beat(plan.media_assets, scene.index)
        beat = _beat_for_index(draft, scene.index)
        score = media.score if media else 0.0
        warnings: list[str] = []
        if score < settings.visual_relevance_min_score:
            warnings.append("Visual relevance score is below the configured minimum.")
        if media is None:
            warnings.append("No selected media for this beat.")
        is_cta = bool(draft and is_cta_scene(scene, draft, settings))
        duration = round(scene.end_second - scene.start_second, 2)
        if is_cta and duration < settings.cta_min_duration_seconds:
            warnings.append("CTA/outro beat is shorter than CTA_MIN_DURATION_SECONDS.")
        alignments.append(
            AssetBeatAlignment(
                beat_index=scene.index,
                narration_excerpt=_excerpt(scene.narration or (beat.narration if beat else "")),
                selected_media_url=media.source_url if media else None,
                query_used=media.query if media else None,
                visual_relevance_score=score,
                duration_allocated=duration,
                is_cta_outro=is_cta,
                warnings=warnings,
            )
        )
    return alignments


def _selected_media_for_beat(
    media_assets: list[MediaAssetCandidate],
    beat_index: int,
) -> MediaAssetCandidate | None:
    candidates = [item for item in media_assets if item.beat_index == beat_index]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item.score, reverse=True)[0]


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


def _beat_for_index(draft: ScriptDraft | None, beat_index: int) -> ScriptSceneBeat | None:
    if draft is None or beat_index < 0 or beat_index >= len(draft.scene_beats):
        return None
    return draft.scene_beats[beat_index]


def _query_match_score(candidate: MediaAssetCandidate, beat: ScriptSceneBeat | None) -> float:
    if beat is None:
        return 0.5
    candidate_tokens = _tokens(f"{candidate.query} {candidate.source_url}")
    target_tokens = _tokens(
        " ".join(
            item
            for item in [
                beat.stock_search_query or "",
                beat.visual_suggestion,
                beat.narration,
                beat.narration_segment or "",
            ]
            if item
        )
    )
    if not target_tokens:
        return 0.5
    return len(candidate_tokens.intersection(target_tokens)) / max(1, len(target_tokens))


def _metadata_match_score(candidate: MediaAssetCandidate, value: str | None) -> float:
    target_tokens = _tokens(value or "")
    if not target_tokens:
        return 0.5
    candidate_tokens = _tokens(f"{candidate.query} {candidate.source_url}")
    return len(candidate_tokens.intersection(target_tokens)) / max(1, len(target_tokens))


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", value.lower())
        if len(token) > 2
        and token not in {"the", "and", "for", "with", "video", "stock", "vertical", "dark"}
    }


def _excerpt(value: str, limit: int = 90) -> str:
    normalized = " ".join(value.split())
    return normalized if len(normalized) <= limit else normalized[: limit - 3] + "..."
