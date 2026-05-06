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
            subtitle_timings=build_subtitle_timings(draft, duration, self.settings),
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
        subtitle_timings = build_subtitle_timings(draft, duration, self.settings)
        scene_timings = build_scene_timing_suggestions(draft, duration, self.settings)
        output_dir = Path(self.settings.tts_cache_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / f"script-{draft.id or draft.draft_uid}-{uuid4().hex[:8]}.{self.settings.tts_output_format}"

        last_error: Exception | None = None
        for attempt in range(self.settings.tts_max_retries + 1):
            try:
                boundary_events = asyncio.run(self._save_with_edge_tts(prepared.chunks, file_path))
                actual_duration = probe_audio_duration_seconds(file_path, self.settings)
                final_duration = actual_duration or duration
                quality = build_tts_quality_metadata(
                    prepared,
                    audio_duration_seconds=final_duration,
                    estimated_script_duration_seconds=draft.estimated_duration_seconds,
                )
                quality["edge_boundary_event_count"] = len(boundary_events)
                quality["edge_boundary_events_sample"] = boundary_events[:12]
                subtitle_timings = build_subtitle_timings(draft, final_duration, self.settings)
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

    async def _save_with_edge_tts(self, chunks: list[str], file_path: Path) -> list[dict]:
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
            return await self._write_edge_tts_part(
                edge_tts=edge_tts,
                text=chunks[0],
                file_path=file_path,
                voice=voice,
                rate=cta_rate if is_cta_tts_chunk(chunks[0], self.settings) else rate,
                chunk_index=0,
            )

        temp_dir = Path(tempfile.mkdtemp(prefix="raatverse-tts-"))
        try:
            part_paths: list[Path] = []
            boundary_events: list[dict] = []
            for index, chunk in enumerate(chunks):
                part_path = temp_dir / f"part-{index:03d}.{self.settings.tts_output_format}"
                chunk_events = await self._write_edge_tts_part(
                    edge_tts=edge_tts,
                    text=chunk,
                    file_path=part_path,
                    voice=voice,
                    rate=cta_rate if is_cta_tts_chunk(chunk, self.settings) else rate,
                    chunk_index=index,
                )
                boundary_events.extend(chunk_events)
                part_paths.append(part_path)
            with file_path.open("wb") as output:
                for part_path in part_paths:
                    output.write(part_path.read_bytes())
            return boundary_events
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
