from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

import httpx

from raatverse_agent.assets.errors import StockMediaProviderError
from raatverse_agent.assets.models import MediaAssetCandidate
from raatverse_agent.config import Settings
from raatverse_agent.script_generation.models import ScriptDraft
from raatverse_agent.services.interfaces import StockMediaProvider


def beat_stock_queries(draft: ScriptDraft, beat) -> list[str]:
    primary = (getattr(beat, "stock_search_query", None) or "").strip()
    location = (getattr(beat, "location", None) or "").strip()
    mood = (getattr(beat, "mood", None) or "").strip()
    motion = (getattr(beat, "camera_motion", None) or "").strip()
    visual = (beat.visual_suggestion or "").strip()
    base_parts = [
        location,
        mood,
        visual,
        draft.category,
        "dark cinematic vertical",
    ]
    fallback = " ".join(part for part in base_parts if part).strip()
    queries = [
        primary,
        fallback,
        f"{location} {mood} night vertical suspense".strip(),
        f"{draft.category} {mood} {motion} horror short vertical".strip(),
        f"{visual[:80]} vertical cinematic stock video".strip(),
    ]
    cleaned: list[str] = []
    for query in queries:
        normalized = " ".join(query.split())
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned or [f"{draft.category} dark cinematic mysterious vertical"]


class MockStockMediaProvider(StockMediaProvider):
    def __init__(self, settings: Settings):
        self.settings = settings

    def search_for_draft(self, draft: ScriptDraft) -> list[MediaAssetCandidate]:
        candidates: list[MediaAssetCandidate] = []
        for index, beat in enumerate(draft.scene_beats):
            query = beat_stock_queries(draft, beat)[0]
            for result_index in range(self.settings.stock_media_results_per_beat):
                candidates.append(
                    MediaAssetCandidate(
                        provider="mock",
                        query=query,
                        media_type="video",
                        source_url=f"mock://raatverse/{draft.id or draft.draft_uid}/beat-{index}/{result_index}",
                        creator_name="RaatVerse mock media",
                        license_note="Mock reference only; replace with licensed stock media before rendering.",
                        local_file_path=None,
                        width=1080,
                        height=1920,
                        duration_seconds=max(3.0, beat.end_second - beat.start_second),
                        beat_index=index,
                        score=1.0 - (result_index * 0.1),
                    )
                )
        return candidates


class PexelsStockMediaProvider(StockMediaProvider):
    def __init__(self, settings: Settings):
        self.settings = settings

    def search_for_draft(self, draft: ScriptDraft) -> list[MediaAssetCandidate]:
        if not self.settings.pexels_api_key:
            raise StockMediaProviderError(
                "PEXELS_API_KEY is not configured. Use STOCK_MEDIA_PROVIDER=mock or --mock for dry runs."
            )
        candidates: list[MediaAssetCandidate] = []
        with httpx.Client(timeout=self.settings.stock_media_timeout_seconds) as client:
            for index, beat in enumerate(draft.scene_beats):
                beat_candidates: list[MediaAssetCandidate] = []
                target_candidates = self.settings.stock_media_results_per_beat * 2
                for query in beat_stock_queries(draft, beat):
                    response = client.get(
                        "https://api.pexels.com/videos/search",
                        headers={"Authorization": self.settings.pexels_api_key},
                        params={
                            "query": query,
                            "orientation": "portrait",
                            "per_page": self.settings.stock_media_results_per_beat,
                        },
                    )
                    response.raise_for_status()
                    beat_candidates = _dedupe_candidates(
                        [*beat_candidates, *self._parse_results(response.json(), query, index)]
                    )
                    if len(beat_candidates) >= target_candidates:
                        break
                candidates.extend(beat_candidates)
        return candidates

    def _parse_results(self, payload: dict, query: str, beat_index: int) -> list[MediaAssetCandidate]:
        results: list[MediaAssetCandidate] = []
        for video in payload.get("videos", []):
            files = video.get("video_files") or []
            source_url = video.get("url") or ""
            width = video.get("width")
            height = video.get("height")
            if files:
                vertical_files = sorted(
                    files,
                    key=lambda item: (
                        not ((item.get("height") or 0) >= (item.get("width") or 0)),
                        -(item.get("height") or 0),
                    ),
                )
                source_url = vertical_files[0].get("link") or source_url
                width = vertical_files[0].get("width") or width
                height = vertical_files[0].get("height") or height
            results.append(
                MediaAssetCandidate(
                    provider="pexels",
                    query=query,
                    media_type="video",
                    source_url=source_url,
                    creator_name=(video.get("user") or {}).get("name"),
                    license_note="Pexels API result; verify current Pexels license and attribution before publishing.",
                    width=width,
                    height=height,
                    duration_seconds=video.get("duration"),
                    beat_index=beat_index,
                    score=1.0,
                )
            )
        return results


class PixabayStockMediaProvider(StockMediaProvider):
    def __init__(self, settings: Settings):
        self.settings = settings

    def search_for_draft(self, draft: ScriptDraft) -> list[MediaAssetCandidate]:
        if not self.settings.pixabay_api_key:
            raise StockMediaProviderError(
                "PIXABAY_API_KEY is not configured. Use STOCK_MEDIA_PROVIDER=mock or --mock for dry runs."
            )
        candidates: list[MediaAssetCandidate] = []
        with httpx.Client(timeout=self.settings.stock_media_timeout_seconds) as client:
            for index, beat in enumerate(draft.scene_beats):
                beat_candidates: list[MediaAssetCandidate] = []
                target_candidates = self.settings.stock_media_results_per_beat * 2
                for query in beat_stock_queries(draft, beat):
                    response = client.get(
                        "https://pixabay.com/api/videos/",
                        params={
                            "key": self.settings.pixabay_api_key,
                            "q": query,
                            "per_page": self.settings.stock_media_results_per_beat,
                            "video_type": "film",
                        },
                    )
                    response.raise_for_status()
                    beat_candidates = _dedupe_candidates(
                        [*beat_candidates, *self._parse_results(response.json(), query, index)]
                    )
                    if len(beat_candidates) >= target_candidates:
                        break
                candidates.extend(beat_candidates)
        return candidates

    def _parse_results(self, payload: dict, query: str, beat_index: int) -> list[MediaAssetCandidate]:
        results: list[MediaAssetCandidate] = []
        for item in payload.get("hits", []):
            videos = item.get("videos") or {}
            selected = videos.get("large") or videos.get("medium") or videos.get("small") or {}
            results.append(
                MediaAssetCandidate(
                    provider="pixabay",
                    query=query,
                    media_type="video",
                    source_url=selected.get("url") or item.get("pageURL") or "",
                    creator_name=item.get("user"),
                    license_note="Pixabay API result; verify current Pixabay content license before publishing.",
                    width=selected.get("width"),
                    height=selected.get("height"),
                    duration_seconds=item.get("duration"),
                    beat_index=beat_index,
                    score=1.0,
                )
            )
        return results


class CombinedStockMediaProvider(StockMediaProvider):
    def __init__(self, providers: list[StockMediaProvider]):
        self.providers = providers

    def search_for_draft(self, draft: ScriptDraft) -> list[MediaAssetCandidate]:
        candidates: list[MediaAssetCandidate] = []
        errors: list[str] = []
        for provider in self.providers:
            try:
                candidates.extend(provider.search_for_draft(draft))
            except StockMediaProviderError as exc:
                errors.append(str(exc))
        if not candidates and errors:
            raise StockMediaProviderError("; ".join(errors))
        return candidates


def create_stock_media_provider(settings: Settings, *, mock: bool = False) -> StockMediaProvider:
    provider = settings.stock_media_provider.strip().lower()
    if mock or provider == "mock":
        return MockStockMediaProvider(settings)
    if provider == "pexels":
        return PexelsStockMediaProvider(settings)
    if provider == "pixabay":
        return PixabayStockMediaProvider(settings)
    if provider == "both":
        return CombinedStockMediaProvider(
            [PexelsStockMediaProvider(settings), PixabayStockMediaProvider(settings)]
        )
    raise ValueError(
        f"Unsupported STOCK_MEDIA_PROVIDER '{settings.stock_media_provider}'. Supported: mock, pexels, pixabay, both."
    )


def ensure_media_cache_dir(settings: Settings) -> Path:
    path = Path(settings.stock_media_cache_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _dedupe_candidates(candidates: list[MediaAssetCandidate]) -> list[MediaAssetCandidate]:
    seen: set[str] = set()
    deduped: list[MediaAssetCandidate] = []
    for candidate in candidates:
        key = candidate.source_url
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped
