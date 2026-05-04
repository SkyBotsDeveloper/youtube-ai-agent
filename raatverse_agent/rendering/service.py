from __future__ import annotations

from raatverse_agent.assets.models import AssetPlan, AudioAsset
from raatverse_agent.assets.quality import analyze_asset_plan
from raatverse_agent.config import Settings
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.rendering.errors import RenderProviderError, RenderWorkflowError
from raatverse_agent.rendering.models import RenderRequest, RenderValidationResult, VideoRender
from raatverse_agent.rendering.renderers import FFmpegVideoRenderer, MockVideoRenderer, VideoRenderProvider
from raatverse_agent.script_generation.models import ScriptDraft


def create_video_renderer(settings: Settings, *, mock: bool = False) -> VideoRenderProvider:
    provider = settings.video_renderer.strip().lower()
    if mock or provider == "mock":
        if not settings.render_mock_enabled and mock:
            raise ValueError("Mock rendering is disabled by RENDER_MOCK_ENABLED=false.")
        return MockVideoRenderer(settings)
    if provider == "ffmpeg":
        return FFmpegVideoRenderer(settings)
    raise ValueError(
        f"Unsupported VIDEO_RENDERER '{settings.video_renderer}'. Supported: mock, ffmpeg."
    )


class RenderWorkflowService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: RaatVerseRepository,
        renderer: VideoRenderProvider,
    ):
        self.settings = settings
        self.repository = repository
        self.renderer = renderer

    def validate_asset_plan(
        self,
        asset_plan_id: int,
        *,
        force: bool = False,
        strict_quality: bool = False,
    ) -> RenderValidationResult:
        issues: list[str] = []
        warnings: list[str] = []
        loaded = self._load_context(asset_plan_id)
        if loaded is None:
            return RenderValidationResult(
                is_valid=False,
                issues=[f"Asset plan {asset_plan_id} was not found."],
            )
        draft, asset_plan, audio_asset = loaded
        if draft.status != "approved":
            issues.append("Related script draft must be approved before rendering.")
        if asset_plan.status != "asset_ready":
            issues.append("Asset plan must be asset_ready before rendering.")
        if audio_asset is None:
            warnings.append("Asset plan has no audio asset; renderer may use silence.")
        elif audio_asset.status != "asset_ready":
            issues.append("Audio asset must be asset_ready before rendering.")
        if not asset_plan.scene_timings:
            warnings.append("Asset plan has no scene timings; renderer will use one fallback scene.")
        if not asset_plan.subtitle_timings:
            warnings.append("Asset plan has no subtitle timings; render will have no captions.")
        quality_warnings = self._quality_warnings(asset_plan, audio_asset, draft)
        warnings.extend(quality_warnings)
        if strict_quality and quality_warnings:
            issues.extend(f"Strict quality check failed: {warning}" for warning in quality_warnings)
        if force:
            warnings.extend(f"Forced despite issue: {issue}" for issue in issues)
            issues = []
        return RenderValidationResult(is_valid=not issues, issues=issues, warnings=warnings)

    def create_render(self, asset_plan_id: int, request: RenderRequest) -> VideoRender:
        validation = self.validate_asset_plan(
            asset_plan_id,
            force=request.force,
            strict_quality=request.strict_quality,
        )
        if not validation.is_valid:
            raise RenderWorkflowError("; ".join(validation.issues))

        loaded = self._load_context(asset_plan_id)
        if loaded is None:
            raise RenderWorkflowError(f"Asset plan {asset_plan_id} was not found.")
        draft, asset_plan, audio_asset = loaded
        provider = "mock" if isinstance(self.renderer, MockVideoRenderer) else "ffmpeg"
        render = VideoRender(
            asset_plan_id=asset_plan.id or asset_plan_id,
            script_draft_id=draft.id or asset_plan.script_draft_id,
            status="render_pending",
            resolution=f"{self.settings.render_width}x{self.settings.render_height}",
            fps=self.settings.render_fps,
            renderer_provider=provider,
        )
        record = self.repository.create_video_render(render)
        saved = self.repository.get_video_render(record.id)
        if saved is None:
            raise RenderWorkflowError("Saved render record could not be loaded.")

        running = self.repository.update_video_render_status(saved.id, "render_running")
        if running is None:
            raise RenderWorkflowError("Render record disappeared before execution.")

        try:
            rendered = self.renderer.render(
                render=running,
                draft=draft,
                asset_plan=asset_plan,
                audio_asset=audio_asset,
            )
        except RenderProviderError as exc:
            failed = self.repository.update_video_render_status(
                running.id,
                "render_failed",
                error_message=str(exc),
            )
            if failed is None:
                raise RenderWorkflowError("Failed render record could not be loaded.") from exc
            return failed

        ready = self.repository.update_video_render_status(
            running.id,
            rendered.status,
            output_path=rendered.output_path,
            preview_path=rendered.preview_path,
            duration_seconds=rendered.duration_seconds,
            ffmpeg_command_summary=rendered.ffmpeg_command_summary,
            error_message=rendered.error_message,
        )
        if ready is None:
            raise RenderWorkflowError("Completed render record could not be loaded.")
        return ready

    def _load_context(self, asset_plan_id: int) -> tuple[ScriptDraft, AssetPlan, AudioAsset | None] | None:
        asset_plan = self.repository.get_asset_plan(asset_plan_id)
        if asset_plan is None:
            return None
        draft = self.repository.get_script_draft(asset_plan.script_draft_id)
        if draft is None:
            return None
        audio_asset = (
            self.repository.get_audio_asset(asset_plan.audio_asset_id)
            if asset_plan.audio_asset_id
            else None
        )
        return draft, asset_plan, audio_asset

    def _quality_warnings(
        self,
        asset_plan: AssetPlan,
        audio_asset: AudioAsset | None,
        draft: ScriptDraft,
    ) -> list[str]:
        warnings: list[str] = []
        report = analyze_asset_plan(asset_plan, self.settings)
        if report.repeated_urls:
            warnings.append(
                f"Repeated media URLs detected across beats: {len(report.repeated_urls)} repeated source(s)."
            )
        if report.unique_media_ratio < 0.70:
            warnings.append(
                f"Only {report.unique_media_ratio:.0%} of beats have unique media; target is at least 70%."
            )
        if audio_asset and audio_asset.duration_seconds:
            max_duration = draft.estimated_duration_seconds * 1.15
            if audio_asset.duration_seconds > max_duration:
                warnings.append(
                    "Audio duration exceeds estimated script duration by more than 15%; "
                    "subtitles/scene timings may drift."
                )
        return warnings


def create_render_workflow_service(
    *,
    settings: Settings,
    repository: RaatVerseRepository,
    mock: bool = False,
) -> RenderWorkflowService:
    return RenderWorkflowService(
        settings=settings,
        repository=repository,
        renderer=create_video_renderer(settings, mock=mock),
    )
