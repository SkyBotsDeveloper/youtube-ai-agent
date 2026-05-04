from __future__ import annotations

import re

from raatverse_agent.assets.models import SceneTimingSuggestion, SubtitleTiming
from raatverse_agent.script_generation.models import ScriptDraft


def estimate_audio_duration_seconds(text: str, words_per_minute: int = 135) -> float:
    words = re.findall(r"[\w']+", text)
    if not words:
        return 0.0
    return round(max(3.0, (len(words) / words_per_minute) * 60), 2)


def build_subtitle_timings(draft: ScriptDraft, duration_seconds: float | None = None) -> list[SubtitleTiming]:
    lines = draft.subtitle_lines or _split_script_into_subtitles(draft.narration_script)
    total_duration = duration_seconds or draft.estimated_duration_seconds
    if not lines:
        return []

    total_chars = sum(max(1, len(line)) for line in lines)
    cursor = 0.0
    timings: list[SubtitleTiming] = []
    for index, line in enumerate(lines):
        share = max(1, len(line)) / total_chars
        line_duration = max(1.2, round(total_duration * share, 2))
        end = total_duration if index == len(lines) - 1 else min(total_duration, cursor + line_duration)
        timings.append(
            SubtitleTiming(
                index=index,
                start_second=round(cursor, 2),
                end_second=round(max(end, cursor + 0.8), 2),
                text=line,
            )
        )
        cursor = end
    return timings


def build_scene_timing_suggestions(
    draft: ScriptDraft,
    duration_seconds: float | None = None,
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
