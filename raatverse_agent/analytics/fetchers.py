from __future__ import annotations

from datetime import date
from hashlib import md5

import httpx

from raatverse_agent.analytics.models import AnalyticsMetricBundle, SnapshotWindow
from raatverse_agent.config import Settings
from raatverse_agent.script_generation.models import ScriptDraft
from raatverse_agent.youtube.models import YouTubeUpload
from raatverse_agent.youtube.oauth import YouTubeOAuthError, get_access_token, load_token_file

ANALYTICS_REQUIRED_SCOPES = (
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
)


class AnalyticsFetchError(RuntimeError):
    pass


class MockAnalyticsFetcher:
    def __init__(self, settings: Settings):
        self.settings = settings

    def fetch_metrics(
        self,
        *,
        upload: YouTubeUpload,
        draft: ScriptDraft,
        snapshot_window: SnapshotWindow,
        start_date: date,
        end_date: date,
    ) -> AnalyticsMetricBundle:
        seed = f"{upload.id}:{upload.youtube_video_id}:{draft.category}:{draft.story_type}:{snapshot_window}"
        digest = md5(seed.encode("utf-8")).hexdigest()
        jitter = int(digest[:4], 16) % 180
        category_multiplier = {
            "horror": 1.25,
            "mystery": 1.1,
            "suspense": 1.05,
            "thriller": 1.0,
            "emotional_twist": 0.95,
            "urban_legend": 1.15,
            "psychological": 1.0,
        }.get(draft.category, 1.0)
        window_multiplier = {
            "manual": 0.8,
            "24h": 1.0,
            "48h": 1.55,
            "7d": 2.8,
        }[snapshot_window]
        views = int((520 + jitter) * category_multiplier * window_multiplier)
        likes = max(1, int(views * (0.065 + ((int(digest[4:6], 16) % 8) / 1000))))
        comments = max(0, int(views * (0.009 + ((int(digest[6:8], 16) % 4) / 1000))))
        shares = max(0, int(views * 0.006))
        average_duration = min(
            float(self.settings.max_video_seconds),
            28.0 + (category_multiplier * 8.0) + (int(digest[8:10], 16) % 12),
        )
        estimated_minutes = round((views * average_duration) / 60.0, 2)
        subscribers_gained = max(0, int(views / 240))
        subscribers_lost = 1 if views > 900 and int(digest[10:12], 16) % 5 == 0 else 0
        return AnalyticsMetricBundle(
            views=views,
            likes=likes,
            comments=comments,
            shares=shares,
            estimated_minutes_watched=estimated_minutes,
            average_view_duration=round(average_duration, 2),
            subscribers_gained=subscribers_gained,
            subscribers_lost=subscribers_lost,
            raw_response_json={
                "mock": True,
                "seed": seed,
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
            },
        )


class YouTubeAnalyticsApiFetcher:
    def __init__(self, settings: Settings):
        self.settings = settings

    def fetch_metrics(
        self,
        *,
        upload: YouTubeUpload,
        draft: ScriptDraft,
        snapshot_window: SnapshotWindow,
        start_date: date,
        end_date: date,
    ) -> AnalyticsMetricBundle:
        if not upload.youtube_video_id:
            raise AnalyticsFetchError("YouTube video id is required before analytics can be fetched.")
        self._ensure_required_scopes()
        try:
            access_token = get_access_token(self.settings)
        except YouTubeOAuthError as exc:
            raise AnalyticsFetchError(str(exc)) from exc

        metrics = (
            "views,likes,comments,shares,estimatedMinutesWatched,"
            "averageViewDuration,subscribersGained,subscribersLost"
        )
        params = {
            "ids": "channel==MINE",
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "metrics": metrics,
            "filters": f"video=={upload.youtube_video_id}",
        }
        headers = {"Authorization": f"Bearer {access_token}"}
        url = f"{self.settings.youtube_analytics_base_url.rstrip('/')}/reports"
        try:
            response = httpx.get(url, params=params, headers=headers, timeout=30)
        except httpx.HTTPError as exc:
            raise AnalyticsFetchError(f"YouTube Analytics request failed: {exc}") from exc

        if response.status_code >= 400:
            raise AnalyticsFetchError(
                f"YouTube Analytics API failed with HTTP {response.status_code}: {response.text[:700]}"
            )

        payload = response.json()
        return self._parse_report(payload)

    def _ensure_required_scopes(self) -> None:
        configured = set(self.settings.youtube_scope_list)
        missing_config = [scope for scope in ANALYTICS_REQUIRED_SCOPES if scope not in configured]
        if missing_config:
            raise AnalyticsFetchError(
                "YOUTUBE_SCOPES is missing analytics scope(s): " + ", ".join(missing_config)
            )

        token = load_token_file(self.settings)
        token_scope = (token or {}).get("scope")
        if token_scope:
            granted = set(str(token_scope).split())
            missing_token = [scope for scope in ANALYTICS_REQUIRED_SCOPES if scope not in granted]
            if missing_token:
                raise AnalyticsFetchError(
                    "Local YouTube token is missing analytics scope(s): "
                    + ", ".join(missing_token)
                    + ". Re-run youtube oauth-url and exchange-code."
                )

    def _parse_report(self, payload: dict) -> AnalyticsMetricBundle:
        headers = [header.get("name") for header in payload.get("columnHeaders", [])]
        rows = payload.get("rows") or []
        if not rows:
            return AnalyticsMetricBundle(raw_response_json=payload)
        first = rows[0]
        values = {str(name): first[index] for index, name in enumerate(headers) if index < len(first)}
        return AnalyticsMetricBundle(
            views=int(values.get("views", 0) or 0),
            likes=int(values.get("likes", 0) or 0),
            comments=int(values.get("comments", 0) or 0),
            shares=int(values.get("shares", 0) or 0),
            estimated_minutes_watched=float(values.get("estimatedMinutesWatched", 0.0) or 0.0),
            average_view_duration=float(values.get("averageViewDuration", 0.0) or 0.0),
            subscribers_gained=int(values.get("subscribersGained", 0) or 0),
            subscribers_lost=int(values.get("subscribersLost", 0) or 0),
            raw_response_json=payload,
        )


def create_analytics_fetcher(settings: Settings, *, mock: bool = False):
    if mock:
        return MockAnalyticsFetcher(settings)
    return YouTubeAnalyticsApiFetcher(settings)
