from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from sqlalchemy import text

from raatverse_agent.config import Settings
from raatverse_agent.db.session import get_engine
from raatverse_agent.ops.models import ReviewQueue, WorkflowRun


def ops_health_payload(
    *,
    settings: Settings,
    queue: ReviewQueue,
    latest_workflow_run: WorkflowRun | None,
) -> dict[str, Any]:
    db_ok, db_error = _db_connectivity(settings)
    output_ok, output_error = _directory_writable(settings.output_dir)
    backup_ok, backup_error = _directory_writable(settings.db_backup_dir)
    ffmpeg_path = shutil.which(settings.ffmpeg_binary)
    warnings = doctor_warnings(settings, db_ok=db_ok, output_ok=output_ok, backup_ok=backup_ok)
    status = "ok" if db_ok and output_ok and not _blocking_warnings(warnings) else "warning"
    return {
        "status": status,
        "channel": settings.channel_name,
        "automation_mode": settings.automation_mode,
        "auto_upload": settings.auto_upload,
        "daily_stop_after_draft": settings.daily_stop_after_draft,
        "db": {
            "ok": db_ok,
            "engine": settings.db_engine,
            "database_url": settings.database_url,
            "error": db_error,
        },
        "storage": {
            "output_dir": settings.output_dir,
            "output_writable": output_ok,
            "output_error": output_error,
            "backup_dir": settings.db_backup_dir,
            "backup_writable": backup_ok,
            "backup_error": backup_error,
        },
        "ffmpeg": {
            "binary": settings.ffmpeg_binary,
            "available": ffmpeg_path is not None,
            "path": ffmpeg_path,
            "required": settings.video_renderer == "ffmpeg",
        },
        "providers": {
            "automation_mode": settings.automation_mode,
            "llm_provider": settings.llm_provider,
            "tts_provider": settings.tts_provider,
            "stock_media_provider": settings.stock_media_provider,
            "video_renderer": settings.video_renderer,
            "notifications_enabled": settings.notifications_enabled,
            "notification_provider": settings.notification_provider,
        },
        "dashboard": {
            "enabled": settings.dashboard_enabled,
            "require_token": settings.dashboard_require_token,
            "protect_reads": settings.dashboard_protect_reads,
            "allowed_hosts": settings.dashboard_allowed_host_list,
            "token_configured": bool(settings.dashboard_admin_token),
        },
        "safety": {
            "auto_upload": settings.auto_upload,
            "confirm_enable_auto_upload": settings.confirm_enable_auto_upload,
            "effective_auto_upload": settings.effective_auto_upload,
            "auto_upload_must_be_approved": settings.auto_upload_must_be_approved,
            "daily_stop_after_draft": settings.daily_stop_after_draft,
        },
        "latest_workflow_run": latest_workflow_run.model_dump(mode="json") if latest_workflow_run else None,
        "pending_review_count": queue.total_pending,
        "warnings": warnings,
    }


def doctor_warnings(
    settings: Settings,
    *,
    db_ok: bool | None = None,
    output_ok: bool | None = None,
    backup_ok: bool | None = None,
) -> list[str]:
    warnings = list(settings.safety_warnings)
    if settings.video_renderer == "ffmpeg" and shutil.which(settings.ffmpeg_binary) is None:
        warnings.append("VIDEO_RENDERER=ffmpeg but FFMPEG_BINARY was not found on PATH.")
    if settings.automation_mode == "real" and settings.llm_provider != "mock" and not settings.llm_api_key:
        warnings.append("Real script generation is selected but LLM_API_KEY is empty.")
    if settings.automation_mode == "real" and not (
        settings.youtube_refresh_token or Path(settings.youtube_token_file).exists()
    ):
        warnings.append("Real mode has no YouTube refresh token or local token file configured.")
    if settings.dashboard_require_token and not settings.dashboard_admin_token:
        warnings.append("Dashboard token protection is enabled, but no admin token is configured.")
    if settings.is_production and not settings.dashboard_require_token:
        warnings.append("APP_ENV=production should set DASHBOARD_REQUIRE_TOKEN=true.")
    if settings.is_production and not settings.dashboard_admin_token:
        warnings.append("APP_ENV=production should set a non-empty DASHBOARD_ADMIN_TOKEN.")
    if settings.is_production and not settings.db_backup_before_upgrade:
        warnings.append("APP_ENV=production should keep DB_BACKUP_BEFORE_UPGRADE=true.")
    if settings.is_production and not settings.release_backup_required:
        warnings.append("APP_ENV=production should keep RELEASE_BACKUP_REQUIRED=true.")
    if settings.is_production and settings.database_url.startswith("sqlite"):
        warnings.append("APP_ENV=production with SQLite should configure backup cron on VPS or Windows Task Scheduler.")
    if settings.is_production and settings.dashboard_allowed_host_list == ("localhost", "127.0.0.1"):
        warnings.append("APP_ENV=production should review DASHBOARD_ALLOWED_HOSTS and reverse proxy configuration.")
    if settings.auto_upload and not settings.confirm_enable_auto_upload:
        warnings.append("AUTO_UPLOAD is true without CONFIRM_ENABLE_AUTO_UPLOAD=true; keep auto upload disabled.")
    if db_ok is False:
        warnings.append("Database connectivity check failed.")
    if output_ok is False:
        warnings.append("Output directory is not writable.")
    if backup_ok is False:
        warnings.append("DB backup directory is not writable.")
    if settings.db_engine == "postgres" and not settings.database_url.startswith(("postgres://", "postgresql://")):
        warnings.append("Postgres engine selected with a non-Postgres DATABASE_URL.")
    return _dedupe(warnings)


def _db_connectivity(settings: Settings) -> tuple[bool, str | None]:
    try:
        with get_engine(settings.database_url).connect() as connection:
            connection.execute(text("select 1"))
        return True, None
    except Exception as exc:
        return False, str(exc)


def _directory_writable(path: str) -> tuple[bool, str | None]:
    try:
        directory = Path(path)
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".raatverse-write-check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True, None
    except Exception as exc:
        return False, str(exc)


def _blocking_warnings(warnings: list[str]) -> bool:
    return any("AUTO_UPLOAD" in warning or "token" in warning.lower() for warning in warnings)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
