from __future__ import annotations

from pathlib import Path

import httpx

from raatverse_agent.assets.errors import AssetWorkflowError, StockMediaProviderError, TTSProviderError
from raatverse_agent.assets.media import create_stock_media_provider
from raatverse_agent.assets.models import AssetPlan, AssetPreparationRequest, AudioAsset, TTSGenerationRequest
from raatverse_agent.assets.tts import create_tts_provider
from raatverse_agent.config import Settings
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.script_generation.models import ScriptDraft
from raatverse_agent.services.interfaces import StockMediaProvider, TTSProvider


class TTSAssetService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: RaatVerseRepository,
        provider: TTSProvider,
    ):
        self.settings = settings
        self.repository = repository
        self.provider = provider

    def generate_for_script(self, script_id: int, request: TTSGenerationRequest) -> AudioAsset:
        draft = self._get_allowed_draft(script_id, force=request.force)
        try:
            audio = self.provider.generate_audio(draft)
            audio.script_draft_id = draft.id or script_id
        except TTSProviderError as exc:
            audio = AudioAsset(
                script_draft_id=script_id,
                provider=self.settings.tts_provider,
                voice=self.settings.tts_voice,
                language=self.settings.tts_language,
                status="asset_failed",
                error_message=str(exc),
            )

        record = self.repository.create_audio_asset(audio)
        saved = self.repository.get_audio_asset(record.id)
        if saved is None:
            raise AssetWorkflowError("Saved audio asset could not be loaded.")
        return saved

    def _get_allowed_draft(self, script_id: int, *, force: bool) -> ScriptDraft:
        draft = self.repository.get_script_draft(script_id)
        if draft is None:
            raise AssetWorkflowError(f"Script draft {script_id} was not found.")
        if draft.status != "approved" and not force:
            raise AssetWorkflowError(
                f"Script draft {script_id} must be approved before TTS generation. Use --force to override."
            )
        return draft


class AssetPreparationService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: RaatVerseRepository,
        tts_provider: TTSProvider,
        media_provider: StockMediaProvider,
    ):
        self.settings = settings
        self.repository = repository
        self.tts_provider = tts_provider
        self.media_provider = media_provider

    def prepare_for_script(self, script_id: int, request: AssetPreparationRequest) -> AssetPlan:
        draft = self._get_allowed_draft(script_id, force=request.force)
        audio = self.repository.get_latest_ready_audio_asset_for_script(script_id)
        if audio is None:
            audio = TTSAssetService(
                settings=self.settings,
                repository=self.repository,
                provider=self.tts_provider,
            ).generate_for_script(script_id, TTSGenerationRequest(mock=request.mock, force=True))

        if audio.status == "asset_failed":
            plan = AssetPlan(
                script_draft_id=script_id,
                audio_asset_id=audio.id,
                provider=self.settings.stock_media_provider,
                status="asset_failed",
                subtitle_timings=audio.subtitle_timings,
                scene_timings=audio.scene_timings,
                error_message=audio.error_message,
            )
            return self._save_plan(plan)

        try:
            media_assets = self.media_provider.search_for_draft(draft)
            download_enabled = (
                request.download_enabled
                if request.download_enabled is not None
                else self.settings.stock_media_download_enabled
            )
            if download_enabled:
                media_assets = self._download_media_candidates(media_assets)
            status = "asset_ready"
            error_message = None
        except (StockMediaProviderError, httpx.HTTPError) as exc:
            media_assets = []
            status = "asset_failed"
            error_message = str(exc)

        plan = AssetPlan(
            script_draft_id=script_id,
            audio_asset_id=audio.id,
            provider=self.settings.stock_media_provider,
            status=status,  # type: ignore[arg-type]
            media_assets=media_assets,
            subtitle_timings=audio.subtitle_timings,
            scene_timings=audio.scene_timings,
            error_message=error_message,
        )
        return self._save_plan(plan)

    def _get_allowed_draft(self, script_id: int, *, force: bool) -> ScriptDraft:
        draft = self.repository.get_script_draft(script_id)
        if draft is None:
            raise AssetWorkflowError(f"Script draft {script_id} was not found.")
        if draft.status != "approved" and not force:
            raise AssetWorkflowError(
                f"Script draft {script_id} must be approved before asset preparation. Use --force to override."
            )
        return draft

    def _save_plan(self, plan: AssetPlan) -> AssetPlan:
        record = self.repository.create_asset_plan(plan)
        saved = self.repository.get_asset_plan(record.id)
        if saved is None:
            raise AssetWorkflowError("Saved asset plan could not be loaded.")
        return saved

    def _download_media_candidates(self, media_assets):
        cache_dir = Path(self.settings.stock_media_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        downloaded = []
        with httpx.Client(timeout=self.settings.stock_media_timeout_seconds) as client:
            for index, candidate in enumerate(media_assets):
                if candidate.provider == "mock" or not candidate.source_url.startswith("http"):
                    downloaded.append(candidate)
                    continue
                extension = "mp4" if candidate.media_type == "video" else "jpg"
                local_path = cache_dir / f"{candidate.provider}-beat{candidate.beat_index}-{index}.{extension}"
                response = client.get(candidate.source_url)
                response.raise_for_status()
                local_path.write_bytes(response.content)
                downloaded.append(candidate.model_copy(update={"local_file_path": str(local_path)}))
        return downloaded


def create_tts_asset_service(
    *,
    settings: Settings,
    repository: RaatVerseRepository,
    mock: bool = False,
) -> TTSAssetService:
    return TTSAssetService(
        settings=settings,
        repository=repository,
        provider=create_tts_provider(settings, mock=mock),
    )


def create_asset_preparation_service(
    *,
    settings: Settings,
    repository: RaatVerseRepository,
    mock: bool = False,
) -> AssetPreparationService:
    return AssetPreparationService(
        settings=settings,
        repository=repository,
        tts_provider=create_tts_provider(settings, mock=mock),
        media_provider=create_stock_media_provider(settings, mock=mock),
    )
