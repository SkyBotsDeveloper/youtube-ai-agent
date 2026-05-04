from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from raatverse_agent.pipeline.models import (
    AnalyticsSnapshotResult,
    CategoryScoreState,
    RenderMetadata,
    ScriptResult,
    StoryIdeaResult,
    ThumbnailMetadata,
    UploadMetadata,
    VisualAssetRef,
    VoiceoverMetadata,
)
from raatverse_agent.assets.models import AudioAsset, MediaAssetCandidate
from raatverse_agent.script_generation.models import ScriptGenerationRequest, ScriptGenerationResponse
from raatverse_agent.script_generation.models import ScriptDraft


class StrategyAgent(ABC):
    @abstractmethod
    def choose_category(
        self,
        categories: Sequence[str],
        category_scores: Sequence[CategoryScoreState],
    ) -> str:
        """Choose the next category for one original daily Short."""

    @abstractmethod
    def score_category_performance(self, views: int, likes: int, uploads: int) -> float:
        """Return a placeholder performance score for future learning logic."""


class ScriptGenerator(ABC):
    @abstractmethod
    def generate(self, idea: StoryIdeaResult, outro_cta: str) -> ScriptResult:
        """Generate a short-form story script from an idea."""


class ScriptDraftGenerator(ABC):
    @abstractmethod
    def generate_draft(self, request: ScriptGenerationRequest) -> ScriptGenerationResponse:
        """Generate a structured script draft for human review."""


class VoiceGenerator(ABC):
    @abstractmethod
    def generate(self, script: ScriptResult) -> VoiceoverMetadata:
        """Generate or describe voiceover audio for a script."""


class TTSProvider(ABC):
    @abstractmethod
    def generate_audio(self, draft: ScriptDraft) -> AudioAsset:
        """Generate narration audio metadata and, when supported, an audio file."""


class VisualProvider(ABC):
    @abstractmethod
    def find_assets(self, script: ScriptResult) -> list[VisualAssetRef]:
        """Find visual references suitable for vertical video assembly."""


class VideoRenderer(ABC):
    @abstractmethod
    def render(
        self,
        script: ScriptResult,
        visuals: Sequence[VisualAssetRef],
        voiceover: VoiceoverMetadata,
    ) -> RenderMetadata:
        """Render a vertical 9:16 video from script, visuals, and voiceover."""


class ThumbnailGenerator(ABC):
    @abstractmethod
    def generate(self, script: ScriptResult) -> ThumbnailMetadata:
        """Generate or describe a thumbnail asset."""


class YouTubeUploader(ABC):
    @abstractmethod
    def prepare_upload(
        self,
        script: ScriptResult,
        render: RenderMetadata,
        thumbnail: ThumbnailMetadata,
    ) -> UploadMetadata:
        """Upload or prepare metadata for a YouTube video."""


class AnalyticsFetcher(ABC):
    @abstractmethod
    def fetch_latest(self, youtube_video_id: str) -> AnalyticsSnapshotResult:
        """Fetch latest analytics for a YouTube video."""


class StockMediaProvider(ABC):
    @abstractmethod
    def search_for_draft(self, draft: ScriptDraft) -> list[MediaAssetCandidate]:
        """Search/select stock media candidates for script scene beats."""
