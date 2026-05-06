from __future__ import annotations

import re

from raatverse_agent.assets.models import AssetPlan, AudioAsset, SceneTimingSuggestion, SubtitleTiming
from raatverse_agent.config import Settings
from raatverse_agent.script_generation.models import ScriptDraft


def estimate_audio_duration_seconds(text: str, words_per_minute: int = 135) -> float:
    words = re.findall(r"[\w']+", text)
    if not words:
        return 0.0
    return round(max(3.0, (len(words) / words_per_minute) * 60), 2)


def build_subtitle_timings(
    draft: ScriptDraft,
    duration_seconds: float | None = None,
    settings: Settings | None = None,
) -> list[SubtitleTiming]:
    lines = _ensure_cta_subtitle_lines(
        draft.subtitle_lines or _split_script_into_subtitles(draft.narration_script),
        draft,
    )
    total_duration = duration_seconds or draft.estimated_duration_seconds
    min_duration = settings.min_subtitle_duration_seconds if settings else 1.2
    if not lines:
        return []

    total_chars = sum(max(1, len(line)) for line in lines)
    cursor = 0.0
    timings: list[SubtitleTiming] = []
    for index, line in enumerate(lines):
        share = max(1, len(line)) / total_chars
        line_duration = max(min_duration, round(total_duration * share, 2))
        end = total_duration if index == len(lines) - 1 else min(total_duration, cursor + line_duration)
        timings.append(
            SubtitleTiming(
                index=index,
                start_second=round(cursor, 2),
                end_second=round(max(end, cursor + min_duration), 2),
                text=line,
            )
        )
        cursor = end
    return timings


def build_scene_timing_suggestions(
    draft: ScriptDraft,
    duration_seconds: float | None = None,
    settings: Settings | None = None,
) -> list[SceneTimingSuggestion]:
    total_duration = duration_seconds or draft.estimated_duration_seconds
    if not draft.scene_beats:
        return [
            SceneTimingSuggestion(
                index=0,
                start_second=0.0,
                end_second=float(total_duration),
                visual_suggestion="Dark cinematic vertical background with slow motion texture.",
                narration=draft.hook,
            )
        ]

    if settings is not None:
        base_plan = AssetPlan(
            script_draft_id=draft.id or 0,
            provider="timing",
            scene_timings=[
                SceneTimingSuggestion(
                    index=index,
                    start_second=float(beat.start_second),
                    end_second=float(beat.end_second),
                    visual_suggestion=beat.visual_suggestion,
                    narration=beat.narration,
                )
                for index, beat in enumerate(draft.scene_beats)
            ],
        )
        aligned, _ = align_asset_plan_timing_to_audio(
            draft=draft,
            asset_plan=base_plan,
            audio_asset=None,
            settings=settings,
            audio_duration_seconds=total_duration,
        )
        return aligned.scene_timings

    scale = total_duration / max(1, draft.estimated_duration_seconds)
    suggestions: list[SceneTimingSuggestion] = []
    for index, beat in enumerate(draft.scene_beats):
        start = round(beat.start_second * scale, 2)
        end = round(min(total_duration, beat.end_second * scale), 2)
        if end <= start:
            end = round(min(total_duration, start + 1.0), 2)
        suggestions.append(
            SceneTimingSuggestion(
                index=index,
                start_second=start,
                end_second=end,
                visual_suggestion=beat.visual_suggestion,
                narration=beat.narration,
            )
        )
    return suggestions


def align_asset_plan_timing_to_audio(
    *,
    draft: ScriptDraft,
    asset_plan: AssetPlan,
    audio_asset: AudioAsset | None,
    settings: Settings,
    audio_duration_seconds: float | None = None,
) -> tuple[AssetPlan, dict]:
    source_scenes = asset_plan.scene_timings or build_scene_timing_suggestions(draft)
    audio_duration = audio_duration_seconds or (
        audio_asset.duration_seconds if audio_asset and audio_asset.duration_seconds else None
    )
    source_duration = _timing_duration(source_scenes, draft.estimated_duration_seconds)
    effective_audio_duration = float(audio_duration or source_duration)
    cta_index = _cta_scene_index(source_scenes, draft, settings)
    cta_source = source_scenes[cta_index] if source_scenes else None
    cta_duration = _required_cta_duration(cta_source, draft, settings)
    non_cta_count = max(0, len(source_scenes) - 1)
    min_story_duration = non_cta_count * settings.min_scene_beat_duration_seconds
    target_duration = max(
        source_duration,
        effective_audio_duration + settings.cta_end_padding_seconds,
        float(draft.estimated_duration_seconds),
        min_story_duration + cta_duration,
    )
    story_duration = target_duration - cta_duration
    if story_duration < min_story_duration:
        story_duration = min_story_duration
        target_duration = story_duration + cta_duration

    story_scenes = [scene for index, scene in enumerate(source_scenes) if index != cta_index]
    story_durations = [max(0.1, scene.end_second - scene.start_second) for scene in story_scenes]
    weight_total = sum(story_durations) or max(1, len(story_scenes))
    allocated_story = [
        max(
            settings.min_scene_beat_duration_seconds,
            story_duration * ((duration / weight_total) if weight_total else 1 / max(1, len(story_scenes))),
        )
        for duration in story_durations
    ]
    allocated_overflow = sum(allocated_story) - story_duration
    if allocated_overflow > 0:
        story_duration += allocated_overflow
        target_duration += allocated_overflow

    aligned_scenes: list[SceneTimingSuggestion] = []
    cursor = 0.0
    story_iter = iter(zip(story_scenes, allocated_story, strict=False))
    for index, source in enumerate(source_scenes):
        if index == cta_index:
            continue
        scene, allocated = next(story_iter)
        start = cursor
        end = cursor + allocated
        aligned_scenes.append(
            scene.model_copy(
                update={
                    "start_second": round(start, 2),
                    "end_second": round(end, 2),
                }
            )
        )
        cursor = end

    cta_start = cursor
    cta_scene = cta_source or SceneTimingSuggestion(
        index=len(source_scenes),
        start_second=cta_start,
        end_second=target_duration,
        visual_suggestion="Dark cinematic RaatVerse outro screen.",
        narration=draft.cta_line,
    )
    aligned_scenes.append(
        cta_scene.model_copy(
            update={
                "start_second": round(cta_start, 2),
                "end_second": round(target_duration, 2),
                "visual_suggestion": "Dark cinematic RaatVerse outro screen with readable subscribe CTA.",
                "narration": draft.cta_line,
            }
        )
    )
    aligned_scenes = [
        scene.model_copy(update={"index": index})
        for index, scene in enumerate(sorted(aligned_scenes, key=lambda item: item.start_second))
    ]
    aligned_subtitles = _build_aligned_subtitle_timings(
        draft=draft,
        source_timings=asset_plan.subtitle_timings,
        total_duration=target_duration,
        cta_start=cta_start,
        cta_duration=cta_duration,
        settings=settings,
    )
    shortest_scene = min((scene.end_second - scene.start_second for scene in aligned_scenes), default=0.0)
    shortest_subtitle = min((item.end_second - item.start_second for item in aligned_subtitles), default=0.0)
    warnings = _timing_warnings(
        cta_duration=cta_duration,
        shortest_scene=shortest_scene,
        shortest_subtitle=shortest_subtitle,
        audio_duration=effective_audio_duration,
        final_duration=target_duration,
        settings=settings,
    )
    report = {
        "actual_audio_duration_seconds": round(effective_audio_duration, 2),
        "final_video_duration_seconds": round(target_duration, 2),
        "cta_duration_seconds": round(cta_duration, 2),
        "shortest_scene_beat_duration_seconds": round(shortest_scene, 2),
        "shortest_subtitle_duration_seconds": round(shortest_subtitle, 2),
        "subtitle_count": len(aligned_subtitles),
        "timing_scaled_to_audio": abs(target_duration - source_duration) > 0.25,
        "warnings": warnings,
    }
    return (
        asset_plan.model_copy(
            update={
                "scene_timings": aligned_scenes,
                "subtitle_timings": aligned_subtitles,
            }
        ),
        report,
    )


def is_cta_scene(scene: SceneTimingSuggestion, draft: ScriptDraft, settings: Settings) -> bool:
    normalized_narration = _normalize_for_match(scene.narration)
    normalized_visual = _normalize_for_match(scene.visual_suggestion)
    cta = _normalize_for_match(draft.cta_line or settings.outro_cta)
    return bool(cta and cta in normalized_narration) or "outro" in normalized_visual


def _split_script_into_subtitles(script: str) -> list[str]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?।])\s+", script) if part.strip()]
    lines: list[str] = []
    for sentence in sentences:
        if len(sentence) <= 90:
            lines.append(sentence)
            continue
        words = sentence.split()
        chunk: list[str] = []
        for word in words:
            chunk.append(word)
            if len(" ".join(chunk)) >= 70:
                lines.append(" ".join(chunk))
                chunk = []
        if chunk:
            lines.append(" ".join(chunk))
    return lines


def _ensure_cta_subtitle_lines(lines: list[str], draft: ScriptDraft) -> list[str]:
    cta_lines = [
        "Agar kahani pasand aayi ho, to RaatVerse ko subscribe karo.",
        "Kal raat ek aur nayi kahani milegi.",
    ]
    normalized_existing = " ".join(_normalize_for_match(line) for line in lines)
    if "raatverse ko subscribe karo" in normalized_existing and "kal raat" in normalized_existing:
        return lines
    without_full_cta = [
        line
        for line in lines
        if _normalize_for_match(line) != _normalize_for_match(draft.cta_line)
    ]
    return [*without_full_cta, *cta_lines]


def _build_aligned_subtitle_timings(
    *,
    draft: ScriptDraft,
    source_timings: list[SubtitleTiming],
    total_duration: float,
    cta_start: float,
    cta_duration: float,
    settings: Settings,
) -> list[SubtitleTiming]:
    source_lines = [item.text for item in source_timings] or draft.subtitle_lines or _split_script_into_subtitles(
        draft.narration_script
    )
    lines = _ensure_cta_subtitle_lines(source_lines, draft)
    cta_lines = lines[-2:] if len(lines) >= 2 else lines
    story_lines = lines[: max(0, len(lines) - len(cta_lines))]
    timings: list[SubtitleTiming] = []
    timings.extend(
        _allocate_subtitle_lines(
            story_lines,
            start=0.0,
            duration=max(0.0, cta_start),
            min_duration=settings.min_subtitle_duration_seconds,
            start_index=0,
        )
    )
    timings.extend(
        _allocate_subtitle_lines(
            cta_lines,
            start=cta_start,
            duration=max(cta_duration, settings.cta_min_duration_seconds),
            min_duration=max(settings.min_subtitle_duration_seconds, settings.cta_min_duration_seconds / max(1, len(cta_lines))),
            start_index=len(timings),
        )
    )
    if timings:
        final = timings[-1]
        timings[-1] = final.model_copy(update={"end_second": round(max(final.end_second, total_duration), 2)})
    return timings


def _allocate_subtitle_lines(
    lines: list[str],
    *,
    start: float,
    duration: float,
    min_duration: float,
    start_index: int,
) -> list[SubtitleTiming]:
    if not lines:
        return []
    total_chars = sum(max(1, len(line)) for line in lines)
    required = len(lines) * min_duration
    duration = max(duration, required)
    cursor = start
    timings: list[SubtitleTiming] = []
    for offset, line in enumerate(lines):
        share = max(1, len(line)) / total_chars
        line_duration = max(min_duration, duration * share)
        end = start + duration if offset == len(lines) - 1 else cursor + line_duration
        timings.append(
            SubtitleTiming(
                index=start_index + offset,
                start_second=round(cursor, 2),
                end_second=round(max(end, cursor + min_duration), 2),
                text=line,
            )
        )
        cursor = end
    return timings


def _cta_scene_index(
    scenes: list[SceneTimingSuggestion],
    draft: ScriptDraft,
    settings: Settings,
) -> int:
    for index, scene in enumerate(scenes):
        if is_cta_scene(scene, draft, settings):
            return index
    return max(0, len(scenes) - 1)


def _required_cta_duration(
    scene: SceneTimingSuggestion | None,
    draft: ScriptDraft,
    settings: Settings,
) -> float:
    source_duration = (scene.end_second - scene.start_second) if scene else 0.0
    estimated_cta_speech = estimate_audio_duration_seconds(draft.cta_line)
    return max(
        settings.cta_min_duration_seconds,
        settings.cta_visual_hold_seconds,
        source_duration,
        estimated_cta_speech + settings.cta_visual_hold_seconds,
    )


def _timing_duration(scenes: list[SceneTimingSuggestion], fallback: float) -> float:
    if scenes:
        return round(max(scene.end_second for scene in scenes), 2)
    return float(fallback)


def _timing_warnings(
    *,
    cta_duration: float,
    shortest_scene: float,
    shortest_subtitle: float,
    audio_duration: float,
    final_duration: float,
    settings: Settings,
) -> list[str]:
    warnings: list[str] = []
    if cta_duration < settings.cta_min_duration_seconds:
        warnings.append("CTA duration is below the configured minimum.")
    if shortest_scene < settings.min_scene_beat_duration_seconds:
        warnings.append("One or more scene beats are below the configured minimum duration.")
    if shortest_subtitle < settings.min_subtitle_duration_seconds:
        warnings.append("One or more subtitle lines are below the configured minimum duration.")
    if audio_duration > final_duration:
        warnings.append("Audio duration is longer than final video duration.")
    return warnings


def _normalize_for_match(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()
