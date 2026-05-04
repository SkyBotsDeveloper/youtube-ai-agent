from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import uuid4

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from raatverse_agent.audit.models import ApprovalEvent, AuditLog, AuditLogCreate
from raatverse_agent.analytics.models import (
    AnalyticsSnapshot as AnalyticsSnapshotSchema,
    CategoryScoreSummary,
    SnapshotWindow,
)
from raatverse_agent.assets.models import (
    AssetPlan,
    AudioAsset,
    MediaAssetCandidate,
    SceneTimingSuggestion,
    SubtitleTiming,
)
from raatverse_agent.db.models import (
    AnalyticsSnapshot as AnalyticsSnapshotRecord,
    AuditLogRecord,
    ApprovalEventRecord,
    AssetPlanRecord,
    AudioAssetRecord,
    CategoryScore,
    PipelineRun,
    ScriptDraftRecord,
    StoryIdea,
    Video,
    VideoRenderRecord,
    WorkflowRunRecord,
    YouTubeUploadRecord,
)
from raatverse_agent.ops.models import WorkflowRun, WorkflowRunUpdate, WorkflowType
from raatverse_agent.pipeline.models import CategoryScoreState
from raatverse_agent.script_generation.models import (
    ScriptDraft,
    ScriptDraftStatus,
    ScriptSceneBeat,
    ScriptValidationResult,
)
from raatverse_agent.rendering.models import VideoRender, RenderStatus
from raatverse_agent.youtube.models import YouTubeUpload, YouTubeUploadStatus


class RaatVerseRepository:
    """Persistence boundary for pipeline, script review, and API operations."""

    def __init__(self, session: Session):
        self.session = session

    def init_category_scores(self, categories: Iterable[str]) -> None:
        existing = {
            score.category
            for score in self.session.scalars(select(CategoryScore)).all()
        }
        for category in categories:
            if category not in existing:
                self.session.add(CategoryScore(category=category))
        self.session.commit()

    def create_audit_log(
        self,
        *,
        actor: str = "system",
        action: str,
        entity_type: str,
        entity_id: int | None = None,
        before_status: str | None = None,
        after_status: str | None = None,
        reason: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict | None = None,
    ) -> AuditLog:
        record = AuditLogRecord(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_status=before_status,
            after_status=after_status,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata_json=dict(metadata or {}),
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return self._audit_log_record_to_schema(record)

    def create_audit_log_from_request(self, log: AuditLogCreate) -> AuditLog:
        return self.create_audit_log(
            actor=log.actor,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            before_status=log.before_status,
            after_status=log.after_status,
            reason=log.reason,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            metadata=log.metadata,
        )

    def _audit_log_record_to_schema(self, record: AuditLogRecord) -> AuditLog:
        return AuditLog(
            id=record.id,
            actor=record.actor,
            action=record.action,
            entity_type=record.entity_type,
            entity_id=record.entity_id,
            before_status=record.before_status,
            after_status=record.after_status,
            reason=record.reason,
            ip_address=record.ip_address,
            user_agent=record.user_agent,
            metadata=dict(record.metadata_json or {}),
            created_at=record.created_at,
        )

    def list_audit_logs(
        self,
        *,
        action: str | None = None,
        entity_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLog]:
        statement = select(AuditLogRecord)
        if action:
            statement = statement.where(AuditLogRecord.action == action)
        if entity_type:
            statement = statement.where(AuditLogRecord.entity_type == entity_type)
        if since:
            statement = statement.where(AuditLogRecord.created_at >= since)
        if until:
            statement = statement.where(AuditLogRecord.created_at <= until)
        rows = self.session.scalars(
            statement.order_by(AuditLogRecord.created_at.desc(), AuditLogRecord.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return [self._audit_log_record_to_schema(row) for row in rows]

    def get_audit_log(self, audit_log_id: int) -> AuditLog | None:
        record = self.session.get(AuditLogRecord, audit_log_id)
        if record is None:
            return None
        return self._audit_log_record_to_schema(record)

    def create_approval_event(
        self,
        *,
        entity_type: str,
        entity_id: int,
        action: str,
        comment: str | None = None,
        actor: str = "system",
    ) -> ApprovalEvent:
        record = ApprovalEventRecord(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            comment=comment,
            actor=actor,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return self._approval_event_record_to_schema(record)

    def _approval_event_record_to_schema(self, record: ApprovalEventRecord) -> ApprovalEvent:
        return ApprovalEvent(
            id=record.id,
            entity_type=record.entity_type,
            entity_id=record.entity_id,
            action=record.action,
            comment=record.comment,
            actor=record.actor,
            created_at=record.created_at,
        )

    def list_approval_events(
        self,
        *,
        entity_type: str | None = None,
        entity_id: int | None = None,
        action: str | None = None,
        limit: int = 50,
    ) -> list[ApprovalEvent]:
        statement = select(ApprovalEventRecord)
        if entity_type:
            statement = statement.where(ApprovalEventRecord.entity_type == entity_type)
        if entity_id is not None:
            statement = statement.where(ApprovalEventRecord.entity_id == entity_id)
        if action:
            statement = statement.where(ApprovalEventRecord.action == action)
        rows = self.session.scalars(
            statement.order_by(ApprovalEventRecord.created_at.desc(), ApprovalEventRecord.id.desc()).limit(limit)
        ).all()
        return [self._approval_event_record_to_schema(row) for row in rows]

    def get_category_score_states(self) -> list[CategoryScoreState]:
        rows = self.session.scalars(select(CategoryScore).order_by(CategoryScore.category)).all()
        return [
            CategoryScoreState(
                category=row.category,
                story_type=row.story_type,
                score=row.avg_performance_score or row.score,
                impressions=row.impressions,
                views=row.views,
                likes=row.likes,
                uploads=row.uploads,
                total_videos=row.total_videos,
                avg_views=row.avg_views,
                avg_likes=row.avg_likes,
                avg_comments=row.avg_comments,
                avg_like_rate=row.avg_like_rate,
                avg_comment_rate=row.avg_comment_rate,
                avg_average_view_duration=row.avg_average_view_duration,
                avg_subscribers_gained=row.avg_subscribers_gained,
                avg_performance_score=row.avg_performance_score or row.score,
                trend_score=row.trend_score,
                confidence=row.confidence,
            )
            for row in rows
        ]

    def _category_score_record_to_schema(self, record: CategoryScore) -> CategoryScoreSummary:
        return CategoryScoreSummary(
            id=record.id,
            category=record.category,
            story_type=record.story_type,
            total_videos=record.total_videos or record.uploads,
            avg_views=record.avg_views,
            avg_likes=record.avg_likes,
            avg_comments=record.avg_comments,
            avg_like_rate=record.avg_like_rate,
            avg_comment_rate=record.avg_comment_rate,
            avg_average_view_duration=record.avg_average_view_duration,
            avg_subscribers_gained=record.avg_subscribers_gained,
            avg_performance_score=record.avg_performance_score or record.score,
            trend_score=record.trend_score,
            confidence=record.confidence,
            last_updated=record.last_updated or record.updated_at,
        )

    def list_category_score_summaries(self) -> list[CategoryScoreSummary]:
        rows = self.session.scalars(
            select(CategoryScore).order_by(CategoryScore.avg_performance_score.desc(), CategoryScore.category)
        ).all()
        return [self._category_score_record_to_schema(row) for row in rows]

    def get_strategy_recommendation_inputs(self) -> list[CategoryScoreSummary]:
        """Return learned category scores for the strategy layer."""

        return self.list_category_score_summaries()

    def upsert_category_score_summary(self, summary: CategoryScoreSummary) -> CategoryScoreSummary:
        record = self.session.scalar(select(CategoryScore).where(CategoryScore.category == summary.category))
        if record is None:
            record = CategoryScore(category=summary.category)
            self.session.add(record)
            self.session.flush()
        record.story_type = summary.story_type
        record.total_videos = summary.total_videos
        record.uploads = summary.total_videos
        record.avg_views = summary.avg_views
        record.avg_likes = summary.avg_likes
        record.avg_comments = summary.avg_comments
        record.avg_like_rate = summary.avg_like_rate
        record.avg_comment_rate = summary.avg_comment_rate
        record.avg_average_view_duration = summary.avg_average_view_duration
        record.avg_subscribers_gained = summary.avg_subscribers_gained
        record.avg_performance_score = summary.avg_performance_score
        record.trend_score = summary.trend_score
        record.confidence = summary.confidence
        record.score = summary.avg_performance_score
        record.views = round(summary.avg_views * summary.total_videos)
        record.likes = round(summary.avg_likes * summary.total_videos)
        record.last_updated = datetime.now(timezone.utc)
        record.updated_at = record.last_updated
        self.session.commit()
        self.session.refresh(record)
        return self._category_score_record_to_schema(record)

    def bump_category_upload(self, category: str) -> None:
        row = self.session.scalar(select(CategoryScore).where(CategoryScore.category == category))
        if row is None:
            row = CategoryScore(category=category)
            self.session.add(row)
            self.session.flush()
        row.uploads += 1
        row.total_videos = max(row.total_videos, row.uploads)
        row.updated_at = datetime.now(timezone.utc)
        row.last_updated = row.updated_at
        self.session.commit()

    def create_story_idea(self, category: str, seed: str, premise: str) -> StoryIdea:
        idea = StoryIdea(
            idea_uid=str(uuid4()),
            category=category,
            seed=seed,
            premise=premise,
            status="mock_generated",
        )
        self.session.add(idea)
        self.session.commit()
        self.session.refresh(idea)
        return idea

    def create_video(
        self,
        *,
        title: str,
        category: str,
        script_text: str,
        duration_seconds: int,
        privacy_status: str,
    ) -> Video:
        video = Video(
            video_uid=str(uuid4()),
            title=title,
            category=category,
            script_text=script_text,
            status="mock_ready_for_review",
            duration_seconds=duration_seconds,
            privacy_status=privacy_status,
        )
        self.session.add(video)
        self.session.commit()
        self.session.refresh(video)
        return video

    def start_pipeline_run(self, mode: str = "mock") -> PipelineRun:
        run = PipelineRun(run_uid=str(uuid4()), mode=mode, status="started")
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def complete_pipeline_run(
        self,
        run: PipelineRun,
        *,
        category: str,
        summary: dict,
        status: str = "completed",
    ) -> PipelineRun:
        run.category = category
        run.status = status
        run.summary_json = summary
        run.finished_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(run)
        return run

    def fail_pipeline_run(self, run: PipelineRun, error_message: str) -> PipelineRun:
        run.status = "failed"
        run.error_message = error_message
        run.finished_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(run)
        return run

    def list_pipeline_runs(self, limit: int = 50) -> list[dict]:
        rows = self.session.scalars(
            select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(limit)
        ).all()
        return [
            {
                "run_uid": row.run_uid,
                "mode": row.mode,
                "status": row.status,
                "category": row.category,
                "started_at": row.started_at.isoformat(),
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                "title": (row.summary_json or {}).get("title"),
                "summary": row.summary_json,
                "error_message": row.error_message,
            }
            for row in rows
        ]

    def create_script_draft(
        self,
        *,
        draft: ScriptDraft,
        validation: ScriptValidationResult,
        raw_response: str | None = None,
    ) -> ScriptDraftRecord:
        record = ScriptDraftRecord(
            draft_uid=draft.draft_uid,
            title=draft.title,
            category=draft.category,
            story_type=draft.story_type,
            hook=draft.hook,
            narration_script=draft.narration_script,
            tts_narration_script=draft.tts_narration_script,
            scene_beats_json=[beat.model_dump() for beat in draft.scene_beats],
            subtitle_lines_json=draft.subtitle_lines,
            cta_line=draft.cta_line,
            estimated_duration_seconds=draft.estimated_duration_seconds,
            language_style=draft.language_style,
            safety_notes_json=draft.safety_notes,
            originality_notes_json=draft.originality_notes,
            validation_json=validation.model_dump(),
            provider=draft.provider,
            prompt_version=draft.prompt_version,
            status=draft.status,
            rejection_reason=draft.rejection_reason,
            raw_response=raw_response,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def _script_draft_record_to_schema(self, record: ScriptDraftRecord) -> ScriptDraft:
        return ScriptDraft(
            id=record.id,
            draft_uid=record.draft_uid,
            title=record.title,
            category=record.category,
            story_type=record.story_type,
            hook=record.hook,
            full_narration_script=record.narration_script,
            narration_hindi_devanagari_for_tts=record.tts_narration_script,
            scene_beats=[ScriptSceneBeat(**beat) for beat in (record.scene_beats_json or [])],
            subtitle_lines=list(record.subtitle_lines_json or []),
            cta_line=record.cta_line,
            estimated_duration_seconds=record.estimated_duration_seconds,
            language_style=record.language_style,
            safety_notes=list(record.safety_notes_json or []),
            originality_notes=list(record.originality_notes_json or []),
            status=record.status,  # type: ignore[arg-type]
            rejection_reason=record.rejection_reason,
            provider=record.provider,
            prompt_version=record.prompt_version,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def list_script_drafts(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ScriptDraft]:
        statement = select(ScriptDraftRecord).order_by(ScriptDraftRecord.created_at.desc()).limit(limit)
        if status:
            statement = (
                select(ScriptDraftRecord)
                .where(ScriptDraftRecord.status == status)
                .order_by(ScriptDraftRecord.created_at.desc())
                .limit(limit)
            )
        rows = self.session.scalars(statement).all()
        return [self._script_draft_record_to_schema(row) for row in rows]

    def get_script_draft(self, draft_id: int) -> ScriptDraft | None:
        record = self.session.get(ScriptDraftRecord, draft_id)
        if record is None:
            return None
        return self._script_draft_record_to_schema(record)

    def update_script_draft_status(
        self,
        draft_id: int,
        status: ScriptDraftStatus,
        reason: str | None = None,
    ) -> ScriptDraft | None:
        record = self.session.get(ScriptDraftRecord, draft_id)
        if record is None:
            return None
        record.status = status
        record.rejection_reason = reason if status in {"rejected", "needs_revision"} else None
        record.updated_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(record)
        return self._script_draft_record_to_schema(record)

    def get_recent_script_context(self, limit: int = 25) -> list[dict]:
        drafts = self.session.scalars(
            select(ScriptDraftRecord)
            .order_by(ScriptDraftRecord.created_at.desc())
            .limit(limit)
        ).all()
        videos = self.session.scalars(
            select(Video)
            .order_by(Video.created_at.desc())
            .limit(limit)
        ).all()
        ideas = self.session.scalars(
            select(StoryIdea)
            .order_by(StoryIdea.created_at.desc())
            .limit(limit)
        ).all()

        context: list[dict] = [
            {
                "source": "script_draft",
                "id": draft.id,
                "title": draft.title,
                "hook": draft.hook,
                "category": draft.category,
                "story_type": draft.story_type,
                "narration_script": draft.narration_script,
            }
            for draft in drafts
        ]
        context.extend(
            {
                "source": "video",
                "id": video.id,
                "title": video.title,
                "hook": "",
                "category": video.category,
                "story_type": "",
                "script_text": video.script_text or "",
            }
            for video in videos
        )
        context.extend(
            {
                "source": "story_idea",
                "id": idea.id,
                "title": idea.seed,
                "hook": "",
                "category": idea.category,
                "story_type": "",
                "script_text": idea.premise,
            }
            for idea in ideas
        )
        return context

    def create_audio_asset(self, audio: AudioAsset) -> AudioAssetRecord:
        record = AudioAssetRecord(
            asset_uid=audio.asset_uid,
            script_draft_id=audio.script_draft_id,
            provider=audio.provider,
            voice=audio.voice,
            language=audio.language,
            file_path=audio.file_path,
            duration_seconds=audio.duration_seconds,
            tts_text=audio.tts_text,
            tts_chunks_json=list(audio.tts_chunks),
            tts_quality_json=dict(audio.tts_quality_metadata),
            subtitle_timings_json=[item.model_dump() for item in audio.subtitle_timings],
            scene_timings_json=[item.model_dump() for item in audio.scene_timings],
            status=audio.status,
            error_message=audio.error_message,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def _audio_asset_record_to_schema(self, record: AudioAssetRecord) -> AudioAsset:
        return AudioAsset(
            id=record.id,
            asset_uid=record.asset_uid,
            script_draft_id=record.script_draft_id,
            provider=record.provider,
            voice=record.voice,
            language=record.language,
            file_path=record.file_path,
            duration_seconds=record.duration_seconds,
            tts_text=record.tts_text,
            tts_chunks=list(record.tts_chunks_json or []),
            tts_quality_metadata=dict(record.tts_quality_json or {}),
            subtitle_timings=[
                SubtitleTiming(**item) for item in (record.subtitle_timings_json or [])
            ],
            scene_timings=[
                SceneTimingSuggestion(**item) for item in (record.scene_timings_json or [])
            ],
            status=record.status,  # type: ignore[arg-type]
            error_message=record.error_message,
            created_at=record.created_at,
        )

    def get_audio_asset(self, audio_asset_id: int) -> AudioAsset | None:
        record = self.session.get(AudioAssetRecord, audio_asset_id)
        if record is None:
            return None
        return self._audio_asset_record_to_schema(record)

    def list_audio_assets(self, limit: int = 50) -> list[AudioAsset]:
        rows = self.session.scalars(
            select(AudioAssetRecord).order_by(AudioAssetRecord.created_at.desc()).limit(limit)
        ).all()
        return [self._audio_asset_record_to_schema(row) for row in rows]

    def get_latest_ready_audio_asset_for_script(self, script_draft_id: int) -> AudioAsset | None:
        record = self.session.scalar(
            select(AudioAssetRecord)
            .where(AudioAssetRecord.script_draft_id == script_draft_id)
            .where(AudioAssetRecord.status == "asset_ready")
            .order_by(AudioAssetRecord.created_at.desc())
            .limit(1)
        )
        if record is None:
            return None
        return self._audio_asset_record_to_schema(record)

    def create_asset_plan(self, plan: AssetPlan) -> AssetPlanRecord:
        record = AssetPlanRecord(
            plan_uid=plan.plan_uid,
            script_draft_id=plan.script_draft_id,
            audio_asset_id=plan.audio_asset_id,
            provider=plan.provider,
            status=plan.status,
            media_assets_json=[item.model_dump() for item in plan.media_assets],
            subtitle_timings_json=[item.model_dump() for item in plan.subtitle_timings],
            scene_timings_json=[item.model_dump() for item in plan.scene_timings],
            error_message=plan.error_message,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def _asset_plan_record_to_schema(self, record: AssetPlanRecord) -> AssetPlan:
        return AssetPlan(
            id=record.id,
            plan_uid=record.plan_uid,
            script_draft_id=record.script_draft_id,
            audio_asset_id=record.audio_asset_id,
            provider=record.provider,
            status=record.status,  # type: ignore[arg-type]
            media_assets=[
                MediaAssetCandidate(**item) for item in (record.media_assets_json or [])
            ],
            subtitle_timings=[
                SubtitleTiming(**item) for item in (record.subtitle_timings_json or [])
            ],
            scene_timings=[
                SceneTimingSuggestion(**item) for item in (record.scene_timings_json or [])
            ],
            error_message=record.error_message,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def get_asset_plan(self, asset_plan_id: int) -> AssetPlan | None:
        record = self.session.get(AssetPlanRecord, asset_plan_id)
        if record is None:
            return None
        return self._asset_plan_record_to_schema(record)

    def list_asset_plans(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[AssetPlan]:
        statement = select(AssetPlanRecord).order_by(AssetPlanRecord.created_at.desc()).limit(limit)
        if status:
            statement = (
                select(AssetPlanRecord)
                .where(AssetPlanRecord.status == status)
                .order_by(AssetPlanRecord.created_at.desc())
                .limit(limit)
            )
        rows = self.session.scalars(statement).all()
        return [self._asset_plan_record_to_schema(row) for row in rows]

    def create_video_render(self, render: VideoRender) -> VideoRenderRecord:
        record = VideoRenderRecord(
            render_uid=render.render_uid,
            asset_plan_id=render.asset_plan_id,
            script_draft_id=render.script_draft_id,
            status=render.status,
            output_path=render.output_path,
            preview_path=render.preview_path,
            duration_seconds=render.duration_seconds,
            resolution=render.resolution,
            fps=render.fps,
            renderer_provider=render.renderer_provider,
            ffmpeg_command_summary=render.ffmpeg_command_summary,
            error_message=render.error_message,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def _video_render_record_to_schema(self, record: VideoRenderRecord) -> VideoRender:
        return VideoRender(
            id=record.id,
            render_uid=record.render_uid,
            asset_plan_id=record.asset_plan_id,
            script_draft_id=record.script_draft_id,
            status=record.status,  # type: ignore[arg-type]
            output_path=record.output_path,
            preview_path=record.preview_path,
            duration_seconds=record.duration_seconds,
            resolution=record.resolution,
            fps=record.fps,
            renderer_provider=record.renderer_provider,
            ffmpeg_command_summary=record.ffmpeg_command_summary,
            error_message=record.error_message,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def update_video_render_status(
        self,
        render_id: int,
        status: RenderStatus,
        *,
        output_path: str | None = None,
        preview_path: str | None = None,
        duration_seconds: float | None = None,
        ffmpeg_command_summary: str | None = None,
        error_message: str | None = None,
    ) -> VideoRender | None:
        record = self.session.get(VideoRenderRecord, render_id)
        if record is None:
            return None
        record.status = status
        if output_path is not None:
            record.output_path = output_path
        if preview_path is not None:
            record.preview_path = preview_path
        if duration_seconds is not None:
            record.duration_seconds = duration_seconds
        if ffmpeg_command_summary is not None:
            record.ffmpeg_command_summary = ffmpeg_command_summary
        record.error_message = error_message
        record.updated_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(record)
        return self._video_render_record_to_schema(record)

    def get_video_render(self, render_id: int) -> VideoRender | None:
        record = self.session.get(VideoRenderRecord, render_id)
        if record is None:
            return None
        return self._video_render_record_to_schema(record)

    def list_video_renders(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[VideoRender]:
        statement = select(VideoRenderRecord).order_by(VideoRenderRecord.created_at.desc()).limit(limit)
        if status:
            statement = (
                select(VideoRenderRecord)
                .where(VideoRenderRecord.status == status)
                .order_by(VideoRenderRecord.created_at.desc())
                .limit(limit)
            )
        rows = self.session.scalars(statement).all()
        return [self._video_render_record_to_schema(row) for row in rows]

    def get_latest_render_for_asset_plan(self, asset_plan_id: int) -> VideoRender | None:
        record = self.session.scalar(
            select(VideoRenderRecord)
            .where(VideoRenderRecord.asset_plan_id == asset_plan_id)
            .order_by(VideoRenderRecord.created_at.desc())
            .limit(1)
        )
        if record is None:
            return None
        return self._video_render_record_to_schema(record)

    def create_youtube_upload(self, upload: YouTubeUpload) -> YouTubeUploadRecord:
        record = YouTubeUploadRecord(
            video_render_id=upload.video_render_id,
            script_draft_id=upload.script_draft_id,
            asset_plan_id=upload.asset_plan_id,
            status=upload.status,
            youtube_video_id=upload.youtube_video_id,
            youtube_url=upload.youtube_url,
            privacy_status=upload.privacy_status,
            scheduled_publish_at=upload.scheduled_publish_at,
            title=upload.title,
            description=upload.description,
            tags_json=upload.tags,
            category_id=upload.category_id,
            contains_synthetic_media=upload.contains_synthetic_media,
            self_declared_made_for_kids=upload.self_declared_made_for_kids,
            upload_provider=upload.upload_provider,
            error_message=upload.error_message,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def _youtube_upload_record_to_schema(self, record: YouTubeUploadRecord) -> YouTubeUpload:
        return YouTubeUpload(
            id=record.id,
            video_render_id=record.video_render_id,
            script_draft_id=record.script_draft_id,
            asset_plan_id=record.asset_plan_id,
            status=record.status,  # type: ignore[arg-type]
            youtube_video_id=record.youtube_video_id,
            youtube_url=record.youtube_url,
            privacy_status=record.privacy_status,
            scheduled_publish_at=record.scheduled_publish_at,
            title=record.title,
            description=record.description,
            tags=list(record.tags_json or []),
            category_id=record.category_id,
            contains_synthetic_media=record.contains_synthetic_media,
            self_declared_made_for_kids=record.self_declared_made_for_kids,
            upload_provider=record.upload_provider,
            error_message=record.error_message,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def get_youtube_upload(self, upload_id: int) -> YouTubeUpload | None:
        record = self.session.get(YouTubeUploadRecord, upload_id)
        if record is None:
            return None
        return self._youtube_upload_record_to_schema(record)

    def get_youtube_upload_by_render_id(self, video_render_id: int) -> YouTubeUpload | None:
        record = self.session.scalar(
            select(YouTubeUploadRecord)
            .where(YouTubeUploadRecord.video_render_id == video_render_id)
            .order_by(YouTubeUploadRecord.created_at.desc())
            .limit(1)
        )
        if record is None:
            return None
        return self._youtube_upload_record_to_schema(record)

    def list_youtube_uploads(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[YouTubeUpload]:
        statement = select(YouTubeUploadRecord).order_by(YouTubeUploadRecord.created_at.desc()).limit(limit)
        if status:
            statement = (
                select(YouTubeUploadRecord)
                .where(YouTubeUploadRecord.status == status)
                .order_by(YouTubeUploadRecord.created_at.desc())
                .limit(limit)
            )
        rows = self.session.scalars(statement).all()
        return [self._youtube_upload_record_to_schema(row) for row in rows]

    def update_youtube_upload_status(
        self,
        upload_id: int,
        status: YouTubeUploadStatus,
        *,
        youtube_video_id: str | None = None,
        youtube_url: str | None = None,
        error_message: str | None = None,
    ) -> YouTubeUpload | None:
        record = self.session.get(YouTubeUploadRecord, upload_id)
        if record is None:
            return None
        record.status = status
        if youtube_video_id is not None:
            record.youtube_video_id = youtube_video_id
        if youtube_url is not None:
            record.youtube_url = youtube_url
        record.error_message = error_message
        record.updated_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(record)
        return self._youtube_upload_record_to_schema(record)

    def approve_youtube_upload(self, upload_id: int) -> YouTubeUpload | None:
        return self.update_youtube_upload_status(upload_id, "upload_approved")

    def update_youtube_upload_schedule(
        self,
        upload_id: int,
        scheduled_publish_at: datetime,
    ) -> YouTubeUpload | None:
        record = self.session.get(YouTubeUploadRecord, upload_id)
        if record is None:
            return None
        record.scheduled_publish_at = scheduled_publish_at
        record.privacy_status = "private"
        record.updated_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(record)
        return self._youtube_upload_record_to_schema(record)

    def create_analytics_snapshot(
        self,
        snapshot: AnalyticsSnapshotSchema,
    ) -> AnalyticsSnapshotRecord:
        record = AnalyticsSnapshotRecord(
            video_id=0,
            youtube_upload_id=snapshot.youtube_upload_id,
            youtube_video_id=snapshot.youtube_video_id,
            script_draft_id=snapshot.script_draft_id,
            category=snapshot.category,
            story_type=snapshot.story_type,
            snapshot_window=snapshot.snapshot_window,
            snapshot_date=snapshot.snapshot_date,
            days_since_upload=snapshot.days_since_upload,
            views=snapshot.views,
            likes=snapshot.likes,
            comments=snapshot.comments,
            shares=snapshot.shares,
            estimated_minutes_watched=snapshot.estimated_minutes_watched,
            average_view_duration=snapshot.average_view_duration,
            average_view_duration_seconds=snapshot.average_view_duration,
            subscribers_gained=snapshot.subscribers_gained,
            subscribers_lost=snapshot.subscribers_lost,
            like_rate=snapshot.like_rate,
            comment_rate=snapshot.comment_rate,
            subscriber_gain_rate=snapshot.subscriber_gain_rate,
            retention_score=snapshot.retention_score,
            performance_score=snapshot.performance_score,
            confidence=snapshot.confidence,
            raw_response_json=snapshot.raw_response_json,
            provider=snapshot.provider,
            status=snapshot.status,
            error_message=snapshot.error_message,
            captured_at=snapshot.snapshot_date,
            created_at=snapshot.created_at,
            updated_at=snapshot.updated_at,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def _analytics_snapshot_record_to_schema(
        self,
        record: AnalyticsSnapshotRecord,
    ) -> AnalyticsSnapshotSchema:
        return AnalyticsSnapshotSchema(
            id=record.id,
            youtube_upload_id=record.youtube_upload_id or 0,
            youtube_video_id=record.youtube_video_id or "",
            script_draft_id=record.script_draft_id or 0,
            category=record.category or "",
            story_type=record.story_type or "",
            snapshot_window=record.snapshot_window or "manual",  # type: ignore[arg-type]
            snapshot_date=record.snapshot_date or record.captured_at,
            days_since_upload=record.days_since_upload or 0.0,
            views=record.views or 0,
            likes=record.likes or 0,
            comments=record.comments or 0,
            shares=record.shares or 0,
            estimated_minutes_watched=record.estimated_minutes_watched or 0.0,
            average_view_duration=record.average_view_duration or record.average_view_duration_seconds,
            subscribers_gained=record.subscribers_gained or 0,
            subscribers_lost=record.subscribers_lost or 0,
            like_rate=record.like_rate or 0.0,
            comment_rate=record.comment_rate or 0.0,
            subscriber_gain_rate=record.subscriber_gain_rate or 0.0,
            retention_score=record.retention_score or 0.0,
            performance_score=record.performance_score or 0.0,
            confidence=record.confidence or 0.0,
            raw_response_json=record.raw_response_json,
            provider=record.provider or "legacy",
            status=record.status,  # type: ignore[arg-type]
            error_message=record.error_message,
            created_at=record.created_at or record.captured_at,
            updated_at=record.updated_at or record.captured_at,
        )

    def list_analytics_snapshots(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[AnalyticsSnapshotSchema]:
        statement = (
            select(AnalyticsSnapshotRecord)
            .order_by(AnalyticsSnapshotRecord.snapshot_date.desc(), AnalyticsSnapshotRecord.id.desc())
            .limit(limit)
        )
        if status:
            statement = (
                select(AnalyticsSnapshotRecord)
                .where(AnalyticsSnapshotRecord.status == status)
                .order_by(AnalyticsSnapshotRecord.snapshot_date.desc(), AnalyticsSnapshotRecord.id.desc())
                .limit(limit)
            )
        rows = self.session.scalars(statement).all()
        return [self._analytics_snapshot_record_to_schema(row) for row in rows]

    def get_analytics_snapshot(self, snapshot_id: int) -> AnalyticsSnapshotSchema | None:
        record = self.session.get(AnalyticsSnapshotRecord, snapshot_id)
        if record is None:
            return None
        return self._analytics_snapshot_record_to_schema(record)

    def get_latest_snapshot_for_upload(
        self,
        youtube_upload_id: int,
        *,
        snapshot_window: SnapshotWindow | None = None,
    ) -> AnalyticsSnapshotSchema | None:
        statement = (
            select(AnalyticsSnapshotRecord)
            .where(AnalyticsSnapshotRecord.youtube_upload_id == youtube_upload_id)
            .order_by(AnalyticsSnapshotRecord.snapshot_date.desc(), AnalyticsSnapshotRecord.id.desc())
            .limit(1)
        )
        if snapshot_window:
            statement = (
                select(AnalyticsSnapshotRecord)
                .where(AnalyticsSnapshotRecord.youtube_upload_id == youtube_upload_id)
                .where(AnalyticsSnapshotRecord.snapshot_window == snapshot_window)
                .order_by(AnalyticsSnapshotRecord.snapshot_date.desc(), AnalyticsSnapshotRecord.id.desc())
                .limit(1)
            )
        record = self.session.scalar(statement)
        if record is None:
            return None
        return self._analytics_snapshot_record_to_schema(record)

    def list_ready_analytics_snapshots(self) -> list[AnalyticsSnapshotSchema]:
        rows = self.session.scalars(
            select(AnalyticsSnapshotRecord)
            .where(AnalyticsSnapshotRecord.status == "snapshot_ready")
            .order_by(AnalyticsSnapshotRecord.snapshot_date.asc())
        ).all()
        return [self._analytics_snapshot_record_to_schema(row) for row in rows]

    def has_snapshot_for_upload_window(
        self,
        youtube_upload_id: int,
        snapshot_window: SnapshotWindow,
    ) -> bool:
        return self.get_latest_snapshot_for_upload(
            youtube_upload_id,
            snapshot_window=snapshot_window,
        ) is not None

    def create_workflow_run(self, run: WorkflowRun) -> WorkflowRunRecord:
        record = WorkflowRunRecord(
            workflow_type=run.workflow_type,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            summary_json=run.summary,
            error_message=run.error_message,
            created_script_id=run.created_script_id,
            created_asset_plan_id=run.created_asset_plan_id,
            created_render_id=run.created_render_id,
            created_upload_id=run.created_upload_id,
            provider_mode=run.provider_mode,
            dry_run=run.dry_run,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def _workflow_run_record_to_schema(self, record: WorkflowRunRecord) -> WorkflowRun:
        return WorkflowRun(
            id=record.id,
            workflow_type=record.workflow_type,  # type: ignore[arg-type]
            status=record.status,  # type: ignore[arg-type]
            started_at=record.started_at,
            finished_at=record.finished_at,
            summary=dict(record.summary_json or {}),
            error_message=record.error_message,
            created_script_id=record.created_script_id,
            created_asset_plan_id=record.created_asset_plan_id,
            created_render_id=record.created_render_id,
            created_upload_id=record.created_upload_id,
            provider_mode=record.provider_mode,
            dry_run=record.dry_run,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def update_workflow_run(self, run_id: int, update: WorkflowRunUpdate) -> WorkflowRun | None:
        record = self.session.get(WorkflowRunRecord, run_id)
        if record is None:
            return None
        if update.status is not None:
            record.status = update.status
        if update.summary is not None:
            record.summary_json = update.summary
        if update.error_message is not None:
            record.error_message = update.error_message
        if update.created_script_id is not None:
            record.created_script_id = update.created_script_id
        if update.created_asset_plan_id is not None:
            record.created_asset_plan_id = update.created_asset_plan_id
        if update.created_render_id is not None:
            record.created_render_id = update.created_render_id
        if update.created_upload_id is not None:
            record.created_upload_id = update.created_upload_id
        if update.started_at is not None:
            record.started_at = update.started_at
        if update.finished_at is not None:
            record.finished_at = update.finished_at
        record.updated_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(record)
        return self._workflow_run_record_to_schema(record)

    def get_workflow_run(self, run_id: int) -> WorkflowRun | None:
        record = self.session.get(WorkflowRunRecord, run_id)
        if record is None:
            return None
        return self._workflow_run_record_to_schema(record)

    def list_workflow_runs(
        self,
        *,
        workflow_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[WorkflowRun]:
        statement = select(WorkflowRunRecord).order_by(WorkflowRunRecord.created_at.desc()).limit(limit)
        if workflow_type or status:
            statement = select(WorkflowRunRecord)
            if workflow_type:
                statement = statement.where(WorkflowRunRecord.workflow_type == workflow_type)
            if status:
                statement = statement.where(WorkflowRunRecord.status == status)
            statement = statement.order_by(WorkflowRunRecord.created_at.desc()).limit(limit)
        rows = self.session.scalars(statement).all()
        return [self._workflow_run_record_to_schema(row) for row in rows]

    def get_latest_workflow_run_by_type(self, workflow_type: WorkflowType) -> WorkflowRun | None:
        record = self.session.scalar(
            select(WorkflowRunRecord)
            .where(WorkflowRunRecord.workflow_type == workflow_type)
            .order_by(WorkflowRunRecord.created_at.desc())
            .limit(1)
        )
        if record is None:
            return None
        return self._workflow_run_record_to_schema(record)
