from __future__ import annotations

from pathlib import Path

from raatverse_agent.assets.models import SubtitleTiming
from raatverse_agent.config import Settings


def ass_timestamp(seconds: float) -> str:
    total_centiseconds = round(seconds * 100)
    centiseconds = total_centiseconds % 100
    total_seconds = total_centiseconds // 100
    secs = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def wrap_subtitle_text(text: str, max_chars: int = 34) -> str:
    words = text.strip().split()
    if not words:
        return text
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and len(candidate) > max_chars:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return r"\N".join(lines[:3])


def build_ass_subtitles(
    *,
    timings: list[SubtitleTiming],
    output_path: Path,
    settings: Settings,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    font_size = max(46, round(settings.render_width * 0.066))
    margin_v = round(settings.render_height * 0.20)
    outline = 5
    shadow = 2

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        f"PlayResX: {settings.render_width}",
        f"PlayResY: {settings.render_height}",
        "",
        "[V4+ Styles]",
        (
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
            "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding"
        ),
        (
            "Style: RaatVerseShorts,Arial,"
            f"{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H99000000,"
            f"-1,0,0,0,100,100,0,0,1,{outline},{shadow},2,80,80,{margin_v},1"
        ),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for timing in timings:
        start = ass_timestamp(timing.start_second)
        end = ass_timestamp(max(timing.end_second, timing.start_second + 0.5))
        text = wrap_subtitle_text(timing.text).replace("{", "").replace("}", "")
        lines.append(
            f"Dialogue: 0,{start},{end},RaatVerseShorts,,0,0,0,,{text}"
        )

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
