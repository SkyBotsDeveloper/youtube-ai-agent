from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

from raatverse_agent.assets.errors import TTSProviderError
from raatverse_agent.assets.models import AudioAsset
from raatverse_agent.assets.timing import (
    build_scene_timing_suggestions,
    build_subtitle_timings,
    estimate_audio_duration_seconds,
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


class MockTTSProvider(TTSProvider):
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate_audio(self, draft: ScriptDraft) -> AudioAsset:
        duration = estimate_audio_duration_seconds(draft.narration_script)
        output_dir = Path(self.settings.tts_cache_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"mock-script-{draft.id or draft.draft_uid}.{self.settings.tts_output_format}"
        file_path = output_dir / filename
        file_path.write_text(
            "Mock narration placeholder for RaatVerse Phase 3.\n"
            f"Title: {draft.title}\n",
            encoding="utf-8",
        )
        return AudioAsset(
            script_draft_id=draft.id or 0,
            provider="mock",
            voice=self.settings.tts_voice,
            language=self.settings.tts_language,
            file_path=str(file_path),
            duration_seconds=duration,
            subtitle_timings=build_subtitle_timings(draft, duration),
            scene_timings=build_scene_timing_suggestions(draft, duration),
            status="asset_ready",
        )


class EdgeFreeTTSProvider(TTSProvider):
    """Free online TTS adapter using edge-tts. No API key is required."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def generate_audio(self, draft: ScriptDraft) -> AudioAsset:
        duration = estimate_audio_duration_seconds(draft.narration_script)
        subtitle_timings = build_subtitle_timings(draft, duration)
        scene_timings = build_scene_timing_suggestions(draft, duration)
        output_dir = Path(self.settings.tts_cache_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / f"script-{draft.id or draft.draft_uid}-{uuid4().hex[:8]}.{self.settings.tts_output_format}"

        last_error: Exception | None = None
        for attempt in range(self.settings.tts_max_retries + 1):
            try:
                asyncio.run(self._save_with_edge_tts(draft.narration_script, file_path))
                return AudioAsset(
                    script_draft_id=draft.id or 0,
                    provider="edge-tts",
                    voice=resolve_tts_voice(self.settings),
                    language=self.settings.tts_language,
                    file_path=str(file_path),
                    duration_seconds=duration,
                    subtitle_timings=subtitle_timings,
                    scene_timings=scene_timings,
                    status="asset_ready",
                )
            except Exception as exc:
                last_error = exc
                if attempt >= self.settings.tts_max_retries:
                    break

        raise TTSProviderError(f"Free TTS generation failed: {last_error}")

    async def _save_with_edge_tts(self, text: str, file_path: Path) -> None:
        try:
            import edge_tts
        except ImportError as exc:
            raise TTSProviderError(
                "edge-tts is not installed. Run pip install -r requirements.txt."
            ) from exc

        communicate = edge_tts.Communicate(
            text,
            resolve_tts_voice(self.settings),
            rate=resolve_edge_rate(self.settings.tts_speaking_rate),
        )
        await communicate.save(str(file_path))


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
