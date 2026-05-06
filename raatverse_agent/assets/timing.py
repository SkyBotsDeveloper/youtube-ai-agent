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
    *,
    tts_text: str | None = None,
    tts_chunks: list[str] | None = None,
    tts_quality_metadata: dict | None = None,
) -> list[SubtitleTiming]:
    if settings is not None and (tts_text or tts_chunks or tts_quality_metadata):
        timings, _ = build_tts_aligned_subtitle_timings(
            draft=draft,
            duration_seconds=duration_seconds,
            settings=settings,
            tts_text=tts_text,
            tts_chunks=tts_chunks or [],
            tts_quality_metadata=tts_quality_metadata or {},
        )
        return timings

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
    if settings is not None:
        return apply_subtitle_timing_offsets(
            timings,
            total_duration=total_duration,
            settings=settings,
        )
    return timings


def build_tts_aligned_subtitle_timings(
    *,
    draft: ScriptDraft,
    duration_seconds: float | None,
    settings: Settings,
    tts_text: str | None = None,
    tts_chunks: list[str] | None = None,
    tts_quality_metadata: dict | None = None,
) -> tuple[list[SubtitleTiming], dict]:
    lines = _ensure_cta_subtitle_lines(
        draft.subtitle_lines or _split_script_into_subtitles(draft.narration_script),
        draft,
    )
    total_duration = float(duration_seconds or draft.estimated_duration_seconds)
    if not lines:
        return [], _empty_subtitle_alignment_diagnostics(settings)

    metadata = tts_quality_metadata or {}
    chunk_timings = _subtitle_chunk_timings(
        tts_chunks=tts_chunks or [],
        tts_text=tts_text or "",
        metadata=metadata,
        total_duration=total_duration,
    )
    boundary_events = _boundary_events_by_chunk(metadata)
    if not chunk_timings:
        chunk_timings = [
            {
                "chunk_index": 0,
                "text": tts_text or draft.narration_script,
                "start_second": 0.0,
                "end_second": total_duration,
                "duration_seconds": total_duration,
                "boundary_event_count": 0,
                "is_cta": False,
            }
        ]

    assignments = _assign_subtitle_lines_to_chunks(lines, chunk_timings)
    timings: list[SubtitleTiming] = []
    boundary_aligned = 0
    fallback_aligned = 0
    deltas: list[float] = []
    invalid_count = 0

    for chunk_position, chunk in enumerate(chunk_timings):
        line_indexes = assignments.get(chunk_position, [])
        if not line_indexes:
            continue
        chunk_events = boundary_events.get(int(chunk.get("chunk_index", chunk_position)), [])
        speech_start, speech_end, boundary_used = _chunk_speech_window(
            chunk,
            chunk_events,
            settings,
        )
        allocated, chunk_deltas, chunk_invalid = _allocate_subtitle_indexes_for_speech_window(
            lines=lines,
            line_indexes=line_indexes,
            speech_start=speech_start,
            speech_end=speech_end,
            settings=settings,
        )
        timings.extend(allocated)
        deltas.extend(chunk_deltas)
        invalid_count += chunk_invalid
        if boundary_used:
            boundary_aligned += len(allocated)
        else:
            fallback_aligned += len(allocated)

    timings = sorted(timings, key=lambda item: (item.start_second, item.index))
    timings = _renumber_subtitles(timings, total_duration)
    diagnostics = _subtitle_alignment_diagnostics(
        settings=settings,
        mode_used="boundary_first" if boundary_aligned else "chunk_estimate",
        boundary_aligned=boundary_aligned,
        fallback_aligned=fallback_aligned,
        deltas=deltas,
        invalid_count=invalid_count,
    )
    return timings, diagnostics


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
    aligned_subtitles, subtitle_diagnostics = _build_aligned_subtitle_timings(
        draft=draft,
        source_timings=asset_plan.subtitle_timings,
        total_duration=target_duration,
        cta_start=cta_start,
        cta_duration=cta_duration,
        settings=settings,
        audio_asset=audio_asset,
        audio_duration=effective_audio_duration,
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
        subtitle_diagnostics=subtitle_diagnostics,
    )
    report = {
        "actual_audio_duration_seconds": round(effective_audio_duration, 2),
        "final_video_duration_seconds": round(target_duration, 2),
        "cta_duration_seconds": round(cta_duration, 2),
        "shortest_scene_beat_duration_seconds": round(shortest_scene, 2),
        "shortest_subtitle_duration_seconds": round(shortest_subtitle, 2),
        "subtitle_count": len(aligned_subtitles),
        "subtitle_timing_mode_used": subtitle_diagnostics.get("mode_used", "unknown"),
        "subtitle_boundary_aligned_lines": int(subtitle_diagnostics.get("boundary_aligned_lines") or 0),
        "subtitle_fallback_aligned_lines": int(subtitle_diagnostics.get("fallback_aligned_lines") or 0),
        "subtitle_earliest_start_delta_seconds": subtitle_diagnostics.get("earliest_start_delta_seconds"),
        "subtitle_latest_start_delta_seconds": subtitle_diagnostics.get("latest_start_delta_seconds"),
        "subtitle_invalid_line_count": int(subtitle_diagnostics.get("invalid_line_count") or 0),
        "subtitle_global_offset_seconds": round(settings.subtitle_global_offset_seconds, 2),
        "subtitle_end_padding_seconds": round(settings.subtitle_end_padding_seconds, 2),
        "subtitle_timing_source": _subtitle_timing_source(audio_asset),
        "cta_tts_mode": _audio_quality_value(audio_asset, "cta_tts_mode", "unknown"),
        "cta_tts_override_used": bool(_audio_quality_value(audio_asset, "cta_tts_override_used", False)),
        "cta_outro_screen_enabled": True,
        "cta_subscribe_button_enabled": settings.outro_subscribe_button_enabled,
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
    audio_asset: AudioAsset | None,
    audio_duration: float,
) -> tuple[list[SubtitleTiming], dict]:
    if audio_asset and (audio_asset.tts_text or audio_asset.tts_chunks or audio_asset.tts_quality_metadata):
        timings, diagnostics = build_tts_aligned_subtitle_timings(
            draft=draft,
            duration_seconds=audio_duration,
            settings=settings,
            tts_text=audio_asset.tts_text,
            tts_chunks=audio_asset.tts_chunks,
            tts_quality_metadata=audio_asset.tts_quality_metadata,
        )
        timings = _fit_subtitles_to_render_duration(timings, total_duration, settings)
        return timings, diagnostics

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
    shifted = apply_subtitle_timing_offsets(
        timings,
        total_duration=total_duration,
        settings=settings,
    )
    return shifted, _fallback_subtitle_diagnostics(shifted, settings)


def apply_subtitle_timing_offsets(
    timings: list[SubtitleTiming],
    *,
    total_duration: float,
    settings: Settings,
) -> list[SubtitleTiming]:
    if not timings:
        return []

    offset = settings.subtitle_global_offset_seconds
    end_padding = settings.subtitle_end_padding_seconds
    min_duration = settings.min_subtitle_duration_seconds
    max_start = max(0.0, total_duration - min_duration)
    starts = [
        round(min(max_start, max(0.0, item.start_second + offset)), 2)
        for item in timings
    ]

    shifted: list[SubtitleTiming] = []
    for index, timing in enumerate(timings):
        start = starts[index]
        natural_end = timing.end_second + offset + end_padding
        next_start = starts[index + 1] if index + 1 < len(starts) else total_duration
        end = min(total_duration, max(natural_end, start + min_duration))
        if index + 1 < len(starts) and end > next_start:
            end = max(start + min_duration, next_start - 0.01)
        shifted.append(
            timing.model_copy(
                update={
                    "start_second": round(start, 2),
                    "end_second": round(max(end, start + min_duration), 2),
                }
            )
        )
    if shifted:
        final = shifted[-1]
        shifted[-1] = final.model_copy(
            update={"end_second": round(max(final.end_second, total_duration), 2)}
        )
    return shifted


def _subtitle_chunk_timings(
    *,
    tts_chunks: list[str],
    tts_text: str,
    metadata: dict,
    total_duration: float,
) -> list[dict]:
    raw_timings = list(metadata.get("tts_chunk_timings") or [])
    if raw_timings:
        return sorted(raw_timings, key=lambda item: float(item.get("start_second") or 0))

    chunks = tts_chunks or ([tts_text] if tts_text else [])
    chunks = [chunk for chunk in chunks if chunk.strip()]
    if not chunks:
        return []
    weights = [max(1, len(_normalize_for_match(chunk))) for chunk in chunks]
    total_weight = sum(weights)
    cursor = 0.0
    timings: list[dict] = []
    for index, (chunk, weight) in enumerate(zip(chunks, weights, strict=False)):
        duration = total_duration * (weight / total_weight) if total_weight else total_duration / len(chunks)
        end = total_duration if index == len(chunks) - 1 else cursor + duration
        timings.append(
            {
                "chunk_index": index,
                "text": chunk,
                "start_second": round(cursor, 3),
                "end_second": round(end, 3),
                "duration_seconds": round(max(0.0, end - cursor), 3),
                "boundary_event_count": 0,
                "is_cta": "subscribe" in _normalize_for_match(chunk) or "\u0938\u092c\u094d\u0938\u0915\u094d\u0930\u093e\u0907\u092c" in chunk,
            }
        )
        cursor = end
    return timings


def _boundary_events_by_chunk(metadata: dict) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = {}
    for event in metadata.get("edge_boundary_events") or []:
        try:
            chunk_index = int(event.get("chunk_index") or 0)
        except (TypeError, ValueError):
            chunk_index = 0
        if "start_second" not in event or "end_second" not in event:
            continue
        grouped.setdefault(chunk_index, []).append(event)
    for events in grouped.values():
        events.sort(key=lambda item: float(item.get("start_second") or 0))
    return grouped


def _assign_subtitle_lines_to_chunks(lines: list[str], chunk_timings: list[dict]) -> dict[int, list[int]]:
    line_weights = [max(1, len(_normalize_for_match(line))) for line in lines]
    chunk_weights = [max(1, len(_normalize_for_match(str(chunk.get("text") or "")))) for chunk in chunk_timings]
    total_line_weight = sum(line_weights) or len(lines)
    total_chunk_weight = sum(chunk_weights) or len(chunk_timings)

    chunk_ranges: list[tuple[float, float]] = []
    cursor = 0.0
    for weight in chunk_weights:
        start = cursor
        cursor += weight / total_chunk_weight
        chunk_ranges.append((start, cursor))

    assignments: dict[int, list[int]] = {index: [] for index in range(len(chunk_timings))}
    line_cursor = 0.0
    for line_index, weight in enumerate(line_weights):
        center = line_cursor + (weight / total_line_weight) / 2
        chunk_index = 0
        for index, (start, end) in enumerate(chunk_ranges):
            if start <= center <= end or index == len(chunk_ranges) - 1:
                chunk_index = index
                break
        assignments.setdefault(chunk_index, []).append(line_index)
        line_cursor += weight / total_line_weight

    empty_indexes = [index for index, values in assignments.items() if not values]
    for index in empty_indexes:
        assignments.pop(index, None)
    if not assignments:
        assignments[len(chunk_timings) - 1] = list(range(len(lines)))
    return assignments


def _chunk_speech_window(
    chunk: dict,
    events: list[dict],
    settings: Settings,
) -> tuple[float, float, bool]:
    chunk_start = float(chunk.get("start_second") or 0.0)
    chunk_end = float(chunk.get("end_second") or chunk_start)
    if settings.subtitle_alignment_mode == "boundary_first" and events:
        event_start = min(float(event.get("start_second") or chunk_start) for event in events)
        event_end = max(float(event.get("end_second") or chunk_end) for event in events)
        return max(chunk_start, event_start), min(max(chunk_end, event_end), event_end), True
    return chunk_start, chunk_end, False


def _allocate_subtitle_indexes_for_speech_window(
    *,
    lines: list[str],
    line_indexes: list[int],
    speech_start: float,
    speech_end: float,
    settings: Settings,
) -> tuple[list[SubtitleTiming], list[float], int]:
    selected_lines = [lines[index] for index in line_indexes]
    weights = [max(1, len(_normalize_for_match(line))) for line in selected_lines]
    total_weight = sum(weights) or len(selected_lines)
    available_duration = max(
        len(selected_lines) * settings.min_subtitle_duration_seconds,
        speech_end - speech_start,
    )
    cursor = speech_start
    timings: list[SubtitleTiming] = []
    deltas: list[float] = []
    invalid_count = 0
    for offset, (line_index, line, weight) in enumerate(zip(line_indexes, selected_lines, weights, strict=False)):
        expected_start = cursor
        duration = max(settings.min_subtitle_duration_seconds, available_duration * (weight / total_weight))
        raw_end = speech_start + available_duration if offset == len(selected_lines) - 1 else cursor + duration
        start = max(expected_start, cursor) + settings.subtitle_global_offset_seconds
        end = max(raw_end + settings.subtitle_global_offset_seconds + settings.subtitle_end_padding_seconds, start + settings.min_subtitle_duration_seconds)
        delta = start - expected_start
        if delta < -settings.subtitle_max_early_start_seconds or delta > settings.subtitle_max_late_start_seconds:
            invalid_count += 1
        timings.append(
            SubtitleTiming(
                index=line_index,
                start_second=round(max(0.0, start), 2),
                end_second=round(max(end, start + settings.min_subtitle_duration_seconds), 2),
                text=line,
            )
        )
        deltas.append(round(delta, 3))
        cursor = raw_end
    return timings, deltas, invalid_count


def _renumber_subtitles(timings: list[SubtitleTiming], total_duration: float) -> list[SubtitleTiming]:
    renumbered: list[SubtitleTiming] = []
    previous_end = 0.0
    for index, timing in enumerate(timings):
        start = max(0.0, timing.start_second)
        end = min(total_duration, max(timing.end_second, start + 0.5))
        if start < previous_end - 0.01:
            start = max(0.0, previous_end)
            end = max(end, start + 0.5)
        renumbered.append(
            timing.model_copy(
                update={
                    "index": index,
                    "start_second": round(start, 2),
                    "end_second": round(min(total_duration, end), 2),
                }
            )
        )
        previous_end = renumbered[-1].end_second
    return renumbered


def _fit_subtitles_to_render_duration(
    timings: list[SubtitleTiming],
    total_duration: float,
    settings: Settings,
) -> list[SubtitleTiming]:
    if not timings:
        return []
    fitted = []
    for timing in timings:
        start = min(max(0.0, timing.start_second), max(0.0, total_duration - settings.min_subtitle_duration_seconds))
        end = min(total_duration, max(timing.end_second, start + settings.min_subtitle_duration_seconds))
        fitted.append(timing.model_copy(update={"start_second": round(start, 2), "end_second": round(end, 2)}))
    final = fitted[-1]
    fitted[-1] = final.model_copy(update={"end_second": round(max(final.end_second, min(total_duration, final.start_second + settings.min_subtitle_duration_seconds)), 2)})
    return _renumber_subtitles(fitted, total_duration)


def _subtitle_alignment_diagnostics(
    *,
    settings: Settings,
    mode_used: str,
    boundary_aligned: int,
    fallback_aligned: int,
    deltas: list[float],
    invalid_count: int,
) -> dict:
    earliest = min(deltas) if deltas else 0.0
    latest = max(deltas) if deltas else 0.0
    warnings: list[str] = []
    if earliest < -settings.subtitle_max_early_start_seconds:
        warnings.append("Subtitle timing starts too early relative to its estimated speech segment.")
    if latest > settings.subtitle_max_late_start_seconds:
        warnings.append("Subtitle timing starts too late relative to its estimated speech segment.")
    if invalid_count:
        warnings.append(f"{invalid_count} subtitle line(s) have invalid timing deltas.")
    return {
        "mode_used": mode_used,
        "boundary_aligned_lines": boundary_aligned,
        "fallback_aligned_lines": fallback_aligned,
        "earliest_start_delta_seconds": round(earliest, 3),
        "latest_start_delta_seconds": round(latest, 3),
        "invalid_line_count": invalid_count,
        "warnings": warnings,
    }


def _fallback_subtitle_diagnostics(timings: list[SubtitleTiming], settings: Settings) -> dict:
    return _subtitle_alignment_diagnostics(
        settings=settings,
        mode_used="scene_duration_fallback",
        boundary_aligned=0,
        fallback_aligned=len(timings),
        deltas=[settings.subtitle_global_offset_seconds for _ in timings],
        invalid_count=0,
    )


def _empty_subtitle_alignment_diagnostics(settings: Settings) -> dict:
    return _subtitle_alignment_diagnostics(
        settings=settings,
        mode_used="empty",
        boundary_aligned=0,
        fallback_aligned=0,
        deltas=[],
        invalid_count=0,
    )


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
    subtitle_diagnostics: dict | None = None,
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
    diagnostics = subtitle_diagnostics or {}
    warnings.extend(str(item) for item in diagnostics.get("warnings", []))
    earliest = diagnostics.get("earliest_start_delta_seconds")
    latest = diagnostics.get("latest_start_delta_seconds")
    if earliest is not None and float(earliest) < -settings.subtitle_max_early_start_seconds:
        warnings.append("Subtitle alignment starts before the related audio beyond the allowed threshold.")
    if latest is not None and float(latest) > settings.subtitle_max_late_start_seconds:
        warnings.append("Subtitle alignment starts after the related audio beyond the allowed threshold.")
    if int(diagnostics.get("invalid_line_count") or 0) > 0:
        warnings.append("Subtitle/audio alignment has invalid line timing.")
    return warnings


def _subtitle_timing_source(audio_asset: AudioAsset | None) -> str:
    if not audio_asset:
        return "estimated_duration_with_offset"
    metadata = audio_asset.tts_quality_metadata or {}
    if int(metadata.get("edge_boundary_event_count") or 0) > 0:
        return "edge_boundary_events_with_offset"
    if audio_asset.duration_seconds:
        return "actual_audio_duration_with_offset"
    return "estimated_duration_with_offset"


def _audio_quality_value(audio_asset: AudioAsset | None, key: str, default):
    if not audio_asset:
        return default
    return (audio_asset.tts_quality_metadata or {}).get(key, default)


def _normalize_for_match(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()
