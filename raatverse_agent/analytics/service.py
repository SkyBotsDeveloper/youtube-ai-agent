from __future__ import annotations

from datetime import datetime, timedelta, timezone

from raatverse_agent.analytics.fetchers import AnalyticsFetchError, create_analytics_fetcher
from raatverse_agent.analytics.models import (
    AnalyticsFetchAllRequest,
    AnalyticsFetchRequest,
    AnalyticsSnapshot,
    DueSnapshotCandidate,
    SnapshotWindow,
)
from raatverse_agent.analytics.scoring import enrich_snapshot_scores
from raatverse_agent.config import Settings
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.youtube.models import YouTubeUpload


class AnalyticsWorkflowError(RuntimeError):
    pass


class AnalyticsWorkflowService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: RaatVerseRepository,
        fetcher,
    ):
        self.settings = settings
        self.repository = repository
        self.fetcher = fetcher

    def fetch_for_upload(
        self,
        upload_id: int,
        request: AnalyticsFetchRequest | None = None,
    ) -> AnalyticsSnapshot:
        request = request or AnalyticsFetchRequest()
        upload = self._load_upload(upload_id)
        draft = self.repository.get_script_draft(upload.script_draft_id)
        if draft is None:
            raise AnalyticsWorkflowError(f"Script draft {upload.script_draft_id} was not found.")
        uploaded_at = self._upload_reference_time(upload)
        snapshot_window = request.snapshot_window or self._select_snapshot_window(uploaded_at)
        start_date, end_date = self._date_range(uploaded_at, snapshot_window)
        days_since_upload = self._days_since(uploaded_at)
        provider_name = "mock" if self.fetcher.__class__.__name__.startswith("Mock") else "youtube-analytics-api"

        try:
            metrics = self.fetcher.fetch_metrics(
                upload=upload,
                draft=draft,
                snapshot_window=snapshot_window,
                start_date=start_date,
                end_date=end_date,
            )
            status = "snapshot_ready" if _has_any_metric(metrics) else "snapshot_empty"
            snapshot = AnalyticsSnapshot(
                youtube_upload_id=upload.id or upload_id,
                youtube_video_id=upload.youtube_video_id or "",
                script_draft_id=draft.id or upload.script_draft_id,
                category=draft.category,
                story_type=draft.story_type,
                snapshot_window=snapshot_window,
                snapshot_date=datetime.now(timezone.utc),
                days_since_upload=round(days_since_upload, 2),
                views=metrics.views,
                likes=metrics.likes,
                comments=metrics.comments,
                shares=metrics.shares,
                estimated_minutes_watched=metrics.estimated_minutes_watched,
                average_view_duration=metrics.average_view_duration,
                subscribers_gained=metrics.subscribers_gained,
                subscribers_lost=metrics.subscribers_lost,
                raw_response_json=metrics.raw_response_json,
                provider=provider_name,
                status=status,  # type: ignore[arg-type]
            )
            previous = self.repository.list_ready_analytics_snapshots()
            category_count = len(
                {
                    item.youtube_upload_id
                    for item in previous
                    if item.category == draft.category and item.youtube_upload_id
                }
            ) + 1
            enriched = enrich_snapshot_scores(
                self.settings,
                snapshot,
                previous,
                category_video_count=category_count,
            )
        except AnalyticsFetchError as exc:
            enriched = AnalyticsSnapshot(
                youtube_upload_id=upload.id or upload_id,
                youtube_video_id=upload.youtube_video_id or "",
                script_draft_id=draft.id or upload.script_draft_id,
                category=draft.category,
                story_type=draft.story_type,
                snapshot_window=snapshot_window,
                snapshot_date=datetime.now(timezone.utc),
                days_since_upload=round(days_since_upload, 2),
                provider=provider_name,
                status="snapshot_failed",
                error_message=str(exc),
            )

        record = self.repository.create_analytics_snapshot(enriched)
        saved = self.repository.get_analytics_snapshot(record.id)
        if saved is None:
            raise AnalyticsWorkflowError("Saved analytics snapshot could not be loaded.")
        return saved

    def fetch_all(self, request: AnalyticsFetchAllRequest | None = None) -> list[AnalyticsSnapshot]:
        request = request or AnalyticsFetchAllRequest()
        if request.only_due:
            upload_ids = [candidate.youtube_upload_id for candidate in self.due_snapshots()]
        else:
            upload_ids = [
                upload.id
                for upload in self.repository.list_youtube_uploads(limit=500)
                if upload.id is not None
                and upload.youtube_video_id
                and upload.status in {"upload_private", "upload_scheduled"}
            ]

        snapshots: list[AnalyticsSnapshot] = []
        seen: set[int] = set()
        for upload_id in upload_ids:
            if upload_id in seen:
                continue
            seen.add(upload_id)
            snapshots.append(
                self.fetch_for_upload(
                    upload_id,
                    AnalyticsFetchRequest(
                        mock=request.mock,
                        snapshot_window=request.snapshot_window,
                    ),
                )
            )
        return snapshots

    def due_snapshots(self) -> list[DueSnapshotCandidate]:
        now = datetime.now(timezone.utc)
        due: list[DueSnapshotCandidate] = []
        thresholds = {"24h": 1.0, "48h": 2.0, "7d": 7.0}
        for upload in self.repository.list_youtube_uploads(limit=500):
            if upload.id is None or not upload.youtube_video_id:
                continue
            if upload.status not in {"upload_private", "upload_scheduled"}:
                continue
            uploaded_at = self._upload_reference_time(upload)
            if upload.scheduled_publish_at and upload.scheduled_publish_at > now:
                continue
            days_since = self._days_since(uploaded_at)
            due_windows: list[SnapshotWindow] = []
            for window in self.settings.analytics_windows:
                if window not in thresholds:
                    continue
                typed_window: SnapshotWindow = window  # type: ignore[assignment]
                if days_since >= thresholds[window] and not self.repository.has_snapshot_for_upload_window(
                    upload.id,
                    typed_window,
                ):
                    due_windows.append(typed_window)
            if due_windows:
                due.append(
                    DueSnapshotCandidate(
                        youtube_upload_id=upload.id,
                        youtube_video_id=upload.youtube_video_id,
                        title=upload.title,
                        status=upload.status,
                        uploaded_at=uploaded_at,
                        days_since_upload=round(days_since, 2),
                        due_windows=due_windows,
                    )
                )
        return due

    def _load_upload(self, upload_id: int) -> YouTubeUpload:
        upload = self.repository.get_youtube_upload(upload_id)
        if upload is None:
            raise AnalyticsWorkflowError(f"YouTube upload {upload_id} was not found.")
        if upload.status not in {"upload_private", "upload_scheduled"}:
            raise AnalyticsWorkflowError("Analytics can only be fetched for uploaded private/scheduled records.")
        if not upload.youtube_video_id:
            raise AnalyticsWorkflowError("YouTube video id is missing; upload must complete before analytics.")
        return upload

    def _upload_reference_time(self, upload: YouTubeUpload) -> datetime:
        if upload.scheduled_publish_at and upload.scheduled_publish_at <= datetime.now(timezone.utc):
            return _ensure_aware(upload.scheduled_publish_at)
        return _ensure_aware(upload.updated_at or upload.created_at)

    def _select_snapshot_window(self, uploaded_at: datetime) -> SnapshotWindow:
        days = self._days_since(uploaded_at)
        if days >= 7:
            return "7d"
        if days >= 2:
            return "48h"
        if days >= 1:
            return "24h"
        return "manual"

    def _date_range(self, uploaded_at: datetime, snapshot_window: SnapshotWindow):
        now = datetime.now(timezone.utc)
        start = uploaded_at.date()
        if snapshot_window == "7d":
            end = min(now.date(), (uploaded_at + timedelta(days=7)).date())
        elif snapshot_window == "48h":
            end = min(now.date(), (uploaded_at + timedelta(days=2)).date())
        elif snapshot_window == "24h":
            end = min(now.date(), (uploaded_at + timedelta(days=1)).date())
        else:
            end = now.date()
        if end < start:
            end = start
        return start, end

    def _days_since(self, uploaded_at: datetime) -> float:
        delta = datetime.now(timezone.utc) - _ensure_aware(uploaded_at)
        return max(delta.total_seconds() / 86400.0, 0.0)


def create_analytics_workflow_service(
    *,
    settings: Settings,
    repository: RaatVerseRepository,
    mock: bool = False,
) -> AnalyticsWorkflowService:
    return AnalyticsWorkflowService(
        settings=settings,
        repository=repository,
        fetcher=create_analytics_fetcher(settings, mock=mock),
    )


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _has_any_metric(metrics) -> bool:
    return any(
        value > 0
        for value in (
            metrics.views,
            metrics.likes,
            metrics.comments,
            metrics.shares,
            metrics.estimated_minutes_watched,
            metrics.average_view_duration,
            metrics.subscribers_gained,
        )
    )
