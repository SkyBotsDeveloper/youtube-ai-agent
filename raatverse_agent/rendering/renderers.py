from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Protocol

from raatverse_agent.assets.models import AssetPlan, AudioAsset, MediaAssetCandidate, SceneTimingSuggestion
from raatverse_agent.assets.timing import is_cta_scene
from raatverse_agent.config import Settings
from raatverse_agent.rendering.errors import RenderProviderError
from raatverse_agent.rendering.models import VideoRender
from raatverse_agent.rendering.subtitles import build_ass_subtitles
from raatverse_agent.script_generation.models import ScriptDraft


class VideoRenderProvider(Protocol):
    def render(
        self,
        *,
        render: VideoRender,
        draft: ScriptDraft,
        asset_plan: AssetPlan,
        audio_asset: AudioAsset | None,
    ) -> VideoRender:
        ...


class MockVideoRenderer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def render(
        self,
        *,
        render: VideoRender,
        draft: ScriptDraft,
        asset_plan: AssetPlan,
        audio_asset: AudioAsset | None,
    ) -> VideoRender:
        output_dir = Path(self.settings.render_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"mock-render-{render.render_uid}.mp4"
        output_path.write_text(
            "Mock RaatVerse render placeholder.\n"
            f"Draft: {draft.title}\n"
            f"Asset plan: {asset_plan.id}\n"
            f"Resolution: {self.settings.render_width}x{self.settings.render_height}\n",
            encoding="utf-8",
        )
        return render.model_copy(
            update={
                "status": "render_ready",
                "output_path": str(output_path),
                "duration_seconds": _duration(asset_plan, draft),
                "resolution": f"{self.settings.render_width}x{self.settings.render_height}",
                "fps": self.settings.render_fps,
                "renderer_provider": "mock",
                "ffmpeg_command_summary": "mock render; ffmpeg not required",
                "error_message": None,
            }
        )


class FFmpegVideoRenderer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def render(
        self,
        *,
        render: VideoRender,
        draft: ScriptDraft,
        asset_plan: AssetPlan,
        audio_asset: AudioAsset | None,
    ) -> VideoRender:
        ffmpeg = shutil.which(self.settings.ffmpeg_binary) or (
            self.settings.ffmpeg_binary if Path(self.settings.ffmpeg_binary).exists() else None
        )
        if ffmpeg is None:
            raise RenderProviderError(
                f"FFmpeg binary '{self.settings.ffmpeg_binary}' was not found. "
                "Install FFmpeg or run with --mock."
            )

        output_dir = Path(self.settings.render_output_dir)
        subtitle_dir = output_dir / "subtitles"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"render-{render.render_uid}.mp4"
        ass_path = subtitle_dir / f"render-{render.render_uid}.ass"
        build_ass_subtitles(
            timings=asset_plan.subtitle_timings,
            output_path=ass_path,
            settings=self.settings,
        )

        command = self._build_ffmpeg_command(
            ffmpeg=ffmpeg,
            draft=draft,
            asset_plan=asset_plan,
            audio_asset=audio_asset,
            ass_path=ass_path,
            output_path=output_path,
        )
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            stderr = completed.stderr.strip()[-1200:]
            raise RenderProviderError(f"FFmpeg render failed: {stderr}")

        return render.model_copy(
            update={
                "status": "render_ready",
                "output_path": str(output_path),
                "preview_path": None,
                "duration_seconds": _duration(asset_plan, draft),
                "resolution": f"{self.settings.render_width}x{self.settings.render_height}",
                "fps": self.settings.render_fps,
                "renderer_provider": "ffmpeg",
                "ffmpeg_command_summary": summarize_command(command),
                "error_message": None,
            }
        )

    def _build_ffmpeg_command(
        self,
        *,
        ffmpeg: str,
        draft: ScriptDraft,
        asset_plan: AssetPlan,
        audio_asset: AudioAsset | None,
        ass_path: Path,
        output_path: Path,
    ) -> list[str]:
        scenes = asset_plan.scene_timings or [
            SceneTimingSuggestion(
                index=0,
                start_second=0,
                end_second=_duration(asset_plan, draft),
                visual_suggestion=draft.hook,
                narration=draft.hook,
            )
        ]
        command = [ffmpeg, "-y"]
        media_inputs: list[MediaAssetCandidate | None] = []
        for scene in scenes:
            duration = max(0.8, scene.end_second - scene.start_second)
            candidate = None if is_cta_scene(scene, draft, self.settings) else _select_local_media(asset_plan.media_assets, scene.index)
            media_inputs.append(candidate)
            if candidate and candidate.local_file_path:
                path = Path(candidate.local_file_path)
                if candidate.media_type.lower() == "image" or path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                    command.extend(["-loop", "1", "-t", f"{duration:.3f}", "-i", str(path)])
                else:
                    command.extend(["-stream_loop", "-1", "-t", f"{duration:.3f}", "-i", str(path)])
            else:
                command.extend(
                    [
                        "-f",
                        "lavfi",
                        "-t",
                        f"{duration:.3f}",
                        "-i",
                        f"color=c=0x08090D:s={self.settings.render_width}x{self.settings.render_height}:r={self.settings.render_fps}",
                    ]
                )

        audio_input_index = len(scenes)
        audio_file = Path(audio_asset.file_path) if audio_asset and audio_asset.file_path else None
        use_real_audio = (
            audio_asset is not None
            and audio_asset.provider != "mock"
            and audio_file is not None
            and audio_file.exists()
        )
        if use_real_audio:
            command.extend(["-i", str(audio_file)])
        else:
            command.extend(
                [
                    "-f",
                    "lavfi",
                    "-t",
                    f"{_duration(asset_plan, draft):.3f}",
                    "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=44100",
                ]
            )

        filter_parts: list[str] = []
        video_labels: list[str] = []
        for index, scene in enumerate(scenes):
            duration = max(0.8, scene.end_second - scene.start_second)
            label = f"v{index}"
            video_labels.append(f"[{label}]")
            scene_filters = (
                f"scale={self.settings.render_width}:{self.settings.render_height}:force_original_aspect_ratio=increase,"
                f"crop={self.settings.render_width}:{self.settings.render_height},"
                f"setsar=1,fps={self.settings.render_fps},format=yuv420p,"
                f"trim=duration={duration:.3f},setpts=PTS-STARTPTS"
            )
            if is_cta_scene(scene, draft, self.settings):
                scene_filters = f"{scene_filters},{outro_screen_drawtext(self.settings)}"
            filter_parts.append(
                f"[{index}:v]"
                f"{scene_filters}"
                f"[{label}]"
            )
        joined_labels = "".join(video_labels)
        filter_parts.append(f"{joined_labels}concat=n={len(video_labels)}:v=1:a=0[vbase]")
        video_chain = "[vbase]"
        subtitle_path = escape_filter_path(ass_path)
        filter_parts.append(f"{video_chain}subtitles='{subtitle_path}'[vsub]")
        video_chain = "[vsub]"
        if self.settings.watermark_enabled:
            draw = watermark_drawtext(self.settings)
            filter_parts.append(f"{video_chain}{draw}[vout]")
        else:
            filter_parts.append(f"{video_chain}null[vout]")

        command.extend(
            [
                "-filter_complex",
                ";".join(filter_parts),
                "-map",
                "[vout]",
                "-map",
                f"{audio_input_index}:a",
                "-t",
                f"{_duration(asset_plan, draft):.3f}",
                "-c:v",
                self.settings.render_video_codec,
                "-preset",
                self.settings.render_preset,
                "-crf",
                str(self.settings.render_crf),
                "-c:a",
                self.settings.render_audio_codec,
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        )
        return command


def _duration(asset_plan: AssetPlan, draft: ScriptDraft) -> float:
    if asset_plan.scene_timings:
        return round(max(item.end_second for item in asset_plan.scene_timings), 2)
    if asset_plan.subtitle_timings:
        return round(max(item.end_second for item in asset_plan.subtitle_timings), 2)
    return float(draft.estimated_duration_seconds)


def _select_local_media(
    media_assets: list[MediaAssetCandidate],
    beat_index: int,
) -> MediaAssetCandidate | None:
    candidates = [
        item
        for item in media_assets
        if item.beat_index == beat_index and item.local_file_path and Path(item.local_file_path).exists()
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: -item.score)[0]


def escape_filter_path(path: Path) -> str:
    return path.resolve().as_posix().replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def watermark_drawtext(settings: Settings) -> str:
    font_size = max(28, round(settings.render_width * 0.036))
    position = settings.watermark_position.strip().lower()
    if position == "bottom-right":
        xy = "x=w-tw-48:y=h-th-160"
    elif position == "bottom-left":
        xy = "x=48:y=h-th-160"
    elif position == "top-left":
        xy = "x=48:y=70"
    else:
        xy = "x=w-tw-48:y=70"
    text = settings.watermark_text.replace(":", r"\:").replace("'", r"\'")
    return (
        "drawtext="
        f"text='{text}':fontcolor=white@0.72:fontsize={font_size}:"
        "box=1:boxcolor=black@0.28:boxborderw=14:"
        f"{xy}:shadowcolor=black@0.65:shadowx=2:shadowy=2"
    )


def outro_screen_drawtext(settings: Settings) -> str:
    brand_size = max(56, round(settings.render_width * 0.07))
    cta_size = max(42, round(settings.render_width * 0.046))
    line1 = _escape_drawtext("Agar kahani pasand aayi ho, to RaatVerse ko subscribe karo.")
    line2 = _escape_drawtext("Kal raat ek aur nayi kahani milegi.")
    brand = _escape_drawtext(settings.watermark_text or "RaatVerse")
    return ",".join(
        [
            "drawtext="
            f"text='{brand}':fontcolor=white:fontsize={brand_size}:"
            "x=(w-tw)/2:y=h*0.34:shadowcolor=black@0.75:shadowx=3:shadowy=3",
            "drawtext="
            f"text='{line1}':fontcolor=white:fontsize={cta_size}:"
            "box=1:boxcolor=black@0.38:boxborderw=18:"
            "x=(w-tw)/2:y=h*0.49:shadowcolor=black@0.85:shadowx=2:shadowy=2",
            "drawtext="
            f"text='{line2}':fontcolor=white:fontsize={cta_size}:"
            "box=1:boxcolor=black@0.38:boxborderw=18:"
            "x=(w-tw)/2:y=h*0.57:shadowcolor=black@0.85:shadowx=2:shadowy=2",
        ]
    )


def _escape_drawtext(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(":", r"\:")
        .replace("'", r"\'")
        .replace(",", r"\,")
    )


def summarize_command(command: list[str], max_length: int = 900) -> str:
    safe_parts = []
    for part in command:
        if len(part) > 180:
            safe_parts.append(part[:177] + "...")
        else:
            safe_parts.append(part)
    summary = " ".join(safe_parts)
    return summary if len(summary) <= max_length else summary[: max_length - 3] + "..."
