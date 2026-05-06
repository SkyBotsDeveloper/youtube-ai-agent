from __future__ import annotations

import asyncio
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4

from raatverse_agent.assets.errors import TTSProviderError
from raatverse_agent.assets.models import AudioAsset
from raatverse_agent.assets.audio_probe import probe_audio_duration_seconds
from raatverse_agent.assets.timing import (
    build_scene_timing_suggestions,
    build_subtitle_timings,
    estimate_audio_duration_seconds,
)
from raatverse_agent.assets.tts_text import (
    build_tts_quality_metadata,
    is_cta_tts_chunk,
    prepare_tts_text,
)
from raatverse_agent.config import Settings
from raatverse_agent.script_generation.models import ScriptDraft
from raatverse_agent.services.interfaces import TTSProvider

EDGE_TTS_VOICES = {
    "female_hindi": "hi-IN-SwaraNeural",
    "male_hindi": "hi-IN-MadhurNeural",
}


def resolve_tts_voice(settings: Settings) -> str:
    return EDGE_TTS_VOICES.get(settings.tts_voice, settings.tts_voice)


def resolve_edge_rate(rate: str) -> str:
    normalized = rate.strip().lower()
    mapping = {
        "slow": "-15%",
        "normal": "+0%",
        "medium": "+0%",
        "fast": "+15%",
    }
    if normalized in mapping:
        return mapping[normalized]
    if normalized.startswith(("+", "-")) and normalized.endswith("%"):
        return normalized
    return "+0%"


def resolve_cta_edge_rate(settings: Settings) -> str:
    base_rate = resolve_edge_rate(settings.tts_speaking_rate)
    if not settings.tts_cta_slower:
        return base_rate
    base_value = int(base_rate.rstrip("%"))
    reduced = max(-50, min(50, base_value - settings.tts_cta_rate_reduction))
    return f"{reduced:+d}%"


class MockTTSProvider(TTSProvider):
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate_audio(self, draft: ScriptDraft) -> AudioAsset:
        prepared = prepare_tts_text(draft, self.settings)
        duration = estimate_audio_duration_seconds(draft.narration_script)
        quality = build_tts_quality_metadata(
            prepared,
            audio_duration_seconds=duration,
            estimated_script_duration_seconds=draft.estimated_duration_seconds,
        )
        quality["tts_chunk_timings"] = _estimated_chunk_timings(prepared.chunks, duration)
        output_dir = Path(self.settings.tts_cache_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"mock-script-{draft.id or draft.draft_uid}.{self.settings.tts_output_format}"
        file_path = output_dir / filename
        file_path.write_text(
            "Mock narration placeholder for RaatVerse Phase 3.\n"
            f"Title: {draft.title}\n"
            f"TTS characters: {prepared.input_characters}\n"
            f"TTS chunks: {len(prepared.chunks)}\n",
            encoding="utf-8",
        )
        return AudioAsset(
            script_draft_id=draft.id or 0,
            provider="mock",
            voice=self.settings.tts_voice,
            language=self.settings.tts_language,
            file_path=str(file_path),
            duration_seconds=duration,
            tts_text=prepared.tts_text,
            tts_chunks=prepared.chunks,
            tts_quality_metadata=quality,
            subtitle_timings=build_subtitle_timings(
                draft,
                duration,
                self.settings,
                tts_text=prepared.tts_text,
                tts_chunks=prepared.chunks,
                tts_quality_metadata=quality,
            ),
            scene_timings=build_scene_timing_suggestions(draft, duration, self.settings),
            status="asset_ready",
        )


class EdgeFreeTTSProvider(TTSProvider):
    """Free online TTS adapter using edge-tts. No API key is required."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def generate_audio(self, draft: ScriptDraft) -> AudioAsset:
        prepared = prepare_tts_text(draft, self.settings)
        duration = estimate_audio_duration_seconds(draft.narration_script)
        quality = build_tts_quality_metadata(
            prepared,
            audio_duration_seconds=duration,
            estimated_script_duration_seconds=draft.estimated_duration_seconds,
        )
        quality["tts_chunk_timings"] = _estimated_chunk_timings(prepared.chunks, duration)
        subtitle_timings = build_subtitle_timings(
            draft,
            duration,
            self.settings,
            tts_text=prepared.tts_text,
            tts_chunks=prepared.chunks,
            tts_quality_metadata=quality,
        )
        scene_timings = build_scene_timing_suggestions(draft, duration, self.settings)
        output_dir = Path(self.settings.tts_cache_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / f"script-{draft.id or draft.draft_uid}-{uuid4().hex[:8]}.{self.settings.tts_output_format}"

        last_error: Exception | None = None
        for attempt in range(self.settings.tts_max_retries + 1):
            try:
                boundary_events, chunk_timings = asyncio.run(self._save_with_edge_tts(prepared.chunks, file_path))
                actual_duration = probe_audio_duration_seconds(file_path, self.settings)
                final_duration = actual_duration or duration
                boundary_events, chunk_timings = _scale_tts_timing_metadata(
                    boundary_events,
                    chunk_timings,
                    final_duration,
                )
                quality = build_tts_quality_metadata(
                    prepared,
                    audio_duration_seconds=final_duration,
                    estimated_script_duration_seconds=draft.estimated_duration_seconds,
                )
                quality["edge_boundary_event_count"] = len(boundary_events)
                quality["edge_boundary_events_sample"] = boundary_events[:12]
                quality["edge_boundary_events"] = boundary_events
                quality["tts_chunk_timings"] = chunk_timings
                subtitle_timings = build_subtitle_timings(
                    draft,
                    final_duration,
                    self.settings,
                    tts_text=prepared.tts_text,
                    tts_chunks=prepared.chunks,
                    tts_quality_metadata=quality,
                )
                scene_timings = build_scene_timing_suggestions(draft, final_duration, self.settings)
                return AudioAsset(
                    script_draft_id=draft.id or 0,
                    provider="edge-tts",
                    voice=resolve_tts_voice(self.settings),
                    language=self.settings.tts_language,
                    file_path=str(file_path),
                    duration_seconds=final_duration,
                    tts_text=prepared.tts_text,
                    tts_chunks=prepared.chunks,
                    tts_quality_metadata=quality,
                    subtitle_timings=subtitle_timings,
                    scene_timings=scene_timings,
                    status="asset_ready",
                )
            except Exception as exc:
                last_error = exc
                if attempt >= self.settings.tts_max_retries:
                    break

        raise TTSProviderError(f"Free TTS generation failed: {last_error}")

    async def _save_with_edge_tts(self, chunks: list[str], file_path: Path) -> tuple[list[dict], list[dict]]:
        try:
            import edge_tts
        except ImportError as exc:
            raise TTSProviderError(
                "edge-tts is not installed. Run pip install -r requirements.txt."
            ) from exc

        if not chunks:
            raise TTSProviderError("Prepared TTS text is empty after normalization.")

        voice = resolve_tts_voice(self.settings)
        rate = resolve_edge_rate(self.settings.tts_speaking_rate)
        cta_rate = resolve_cta_edge_rate(self.settings)
        if len(chunks) == 1:
            boundary_events = await self._write_edge_tts_part(
                edge_tts=edge_tts,
                text=chunks[0],
                file_path=file_path,
                voice=voice,
                rate=cta_rate if is_cta_tts_chunk(chunks[0], self.settings) else rate,
                chunk_index=0,
            )
            duration = probe_audio_duration_seconds(file_path, self.settings) or estimate_audio_duration_seconds(chunks[0])
            chunk_timing = _chunk_timing(0, chunks[0], 0.0, duration, cta_rate if is_cta_tts_chunk(chunks[0], self.settings) else rate, boundary_events)
            return _with_absolute_boundary_times(boundary_events, chunk_start_seconds=0.0), [chunk_timing]

        temp_dir = Path(tempfile.mkdtemp(prefix="raatverse-tts-"))
        try:
            part_paths: list[Path] = []
            boundary_events: list[dict] = []
            chunk_timings: list[dict] = []
            cursor = 0.0
            for index, chunk in enumerate(chunks):
                part_path = temp_dir / f"part-{index:03d}.{self.settings.tts_output_format}"
                chunk_rate = cta_rate if is_cta_tts_chunk(chunk, self.settings) else rate
                chunk_events = await self._write_edge_tts_part(
                    edge_tts=edge_tts,
                    text=chunk,
                    file_path=part_path,
                    voice=voice,
                    rate=chunk_rate,
                    chunk_index=index,
                )
                part_duration = probe_audio_duration_seconds(part_path, self.settings) or estimate_audio_duration_seconds(chunk)
                absolute_events = _with_absolute_boundary_times(chunk_events, chunk_start_seconds=cursor)
                boundary_events.extend(absolute_events)
                chunk_timings.append(_chunk_timing(index, chunk, cursor, cursor + part_duration, chunk_rate, absolute_events))
                cursor += part_duration
                part_paths.append(part_path)
            with file_path.open("wb") as output:
                for part_path in part_paths:
                    output.write(part_path.read_bytes())
            return boundary_events, chunk_timings
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def _write_edge_tts_part(
        self,
        *,
        edge_tts,
        text: str,
        file_path: Path,
        voice: str,
        rate: str,
        chunk_index: int,
    ) -> list[dict]:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        boundary_events: list[dict] = []
        with file_path.open("wb") as audio_file:
            async for event in communicate.stream():
                event_type = str(event.get("type") or event.get("Type") or "").lower()
                if event_type == "audio":
                    data = event.get("data") or event.get("Data")
                    if data:
                        audio_file.write(data)
                elif "boundary" in event_type:
                    boundary_events.append(
                        {
                            "chunk_index": chunk_index,
                            "type": event.get("type") or event.get("Type"),
                            "offset": event.get("offset") or event.get("Offset"),
                            "duration": event.get("duration") or event.get("Duration"),
                            "text": event.get("text") or event.get("Text"),
                            "rate": rate,
                        }
                    )
        return boundary_events


def _edge_time_to_seconds(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return 0.0
    return number / 10_000_000


def _with_absolute_boundary_times(
    events: list[dict],
    *,
    chunk_start_seconds: float,
) -> list[dict]:
    normalized: list[dict] = []
    for event in events:
        offset_seconds = _edge_time_to_seconds(event.get("offset"))
        duration_seconds = _edge_time_to_seconds(event.get("duration")) or 0.0
        if offset_seconds is None:
            normalized.append(dict(event))
            continue
        start = chunk_start_seconds + offset_seconds
        normalized.append(
            {
                **event,
                "start_second": round(start, 3),
                "end_second": round(start + duration_seconds, 3),
                "duration_seconds": round(duration_seconds, 3),
            }
        )
    return normalized


def _chunk_timing(
    index: int,
    text: str,
    start_second: float,
    end_second: float,
    rate: str,
    boundary_events: list[dict],
) -> dict:
    return {
        "chunk_index": index,
        "text": text,
        "start_second": round(start_second, 3),
        "end_second": round(max(end_second, start_second), 3),
        "duration_seconds": round(max(0.0, end_second - start_second), 3),
        "rate": rate,
        "is_cta": is_cta_tts_chunk(text),
        "boundary_event_count": len(boundary_events),
    }


def _scale_tts_timing_metadata(
    boundary_events: list[dict],
    chunk_timings: list[dict],
    final_duration: float,
) -> tuple[list[dict], list[dict]]:
    raw_duration = max(
        [float(item.get("end_second") or 0) for item in chunk_timings]
        + [float(item.get("end_second") or 0) for item in boundary_events],
        default=0.0,
    )
    if raw_duration <= 0 or final_duration <= 0:
        return boundary_events, chunk_timings
    ratio = final_duration / raw_duration
    if abs(ratio - 1.0) < 0.01:
        return boundary_events, chunk_timings

    scaled_events: list[dict] = []
    for event in boundary_events:
        updated = dict(event)
        if "start_second" in updated:
            updated["start_second"] = round(float(updated["start_second"]) * ratio, 3)
        if "end_second" in updated:
            updated["end_second"] = round(float(updated["end_second"]) * ratio, 3)
        if "duration_seconds" in updated:
            updated["duration_seconds"] = round(float(updated["duration_seconds"]) * ratio, 3)
        scaled_events.append(updated)

    scaled_chunks: list[dict] = []
    for chunk in chunk_timings:
        updated = dict(chunk)
        updated["start_second"] = round(float(updated.get("start_second") or 0) * ratio, 3)
        updated["end_second"] = round(float(updated.get("end_second") or 0) * ratio, 3)
        updated["duration_seconds"] = round(max(0.0, updated["end_second"] - updated["start_second"]), 3)
        scaled_chunks.append(updated)
    return scaled_events, scaled_chunks


def _estimated_chunk_timings(chunks: list[str], total_duration: float) -> list[dict]:
    chunks = [chunk for chunk in chunks if chunk.strip()]
    if not chunks:
        return []
    weights = [max(1, len(chunk)) for chunk in chunks]
    total_weight = sum(weights)
    cursor = 0.0
    timings: list[dict] = []
    for index, (chunk, weight) in enumerate(zip(chunks, weights, strict=False)):
        duration = total_duration * (weight / total_weight) if total_weight else total_duration / len(chunks)
        end = total_duration if index == len(chunks) - 1 else cursor + duration
        timings.append(_chunk_timing(index, chunk, cursor, end, "estimated", []))
        cursor = end
    return timings


class LocalPlaceholderTTSProvider(TTSProvider):
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate_audio(self, draft: ScriptDraft) -> AudioAsset:
        raise TTSProviderError(
            "Local/offline TTS is a planned extension point and is not implemented in Phase 3."
        )


def create_tts_provider(settings: Settings, *, mock: bool = False) -> TTSProvider:
    provider = settings.tts_provider.strip().lower()
    if mock or provider == "mock":
        return MockTTSProvider(settings)
    if provider in {"free", "edge", "edge-tts"}:
        return EdgeFreeTTSProvider(settings)
    if provider in {"local", "offline"}:
        return LocalPlaceholderTTSProvider(settings)
    raise ValueError(
        f"Unsupported TTS_PROVIDER '{settings.tts_provider}'. Supported: mock, free, edge-tts, local."
    )
