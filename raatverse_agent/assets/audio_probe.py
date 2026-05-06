from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from raatverse_agent.config import Settings


def probe_audio_duration_seconds(path: str | Path | None, settings: Settings) -> float | None:
    if not path:
        return None
    audio_path = Path(path)
    if not audio_path.exists():
        return None
    ffprobe = _resolve_ffprobe(settings)
    if ffprobe is None:
        return None
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    try:
        payload = json.loads(completed.stdout or "{}")
        duration = float((payload.get("format") or {}).get("duration") or 0.0)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return round(duration, 2) if duration > 0 else None


def _resolve_ffprobe(settings: Settings) -> str | None:
    ffmpeg_path = Path(settings.ffmpeg_binary)
    candidates: list[str] = []
    if ffmpeg_path.name.lower().startswith("ffmpeg"):
        ffprobe_name = ffmpeg_path.name.replace("ffmpeg", "ffprobe", 1)
        candidates.append(str(ffmpeg_path.with_name(ffprobe_name)))
    candidates.extend(["ffprobe", "ffprobe.exe"])
    for candidate in candidates:
        resolved = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if resolved:
            return resolved
    return None
