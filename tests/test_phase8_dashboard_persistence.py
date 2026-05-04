import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raatverse_agent.api.main import app
from raatverse_agent.config import Settings, get_settings
from raatverse_agent.db.persistence import (
    PersistenceError,
    backup_database,
    export_database_json,
    import_database_json,
    list_backups,
    restore_database,
)
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.db.session import initialize_database, session_scope
from raatverse_agent.notifications.providers import NotificationError
from raatverse_agent.notifications.service import NotificationService
from raatverse_agent.ops.models import WorkflowRequest, WorkflowRunUpdate
from raatverse_agent.ops.workflow import WorkflowOrchestrationService


def _settings(tmp_path, **overrides):
    values = {
        "database_url": f"sqlite:///{(tmp_path / 'phase8.db').as_posix()}",
        "db_backup_dir": str(tmp_path / "backups"),
        "db_export_dir": str(tmp_path / "exports"),
        "workflow_log_dir": str(tmp_path / "logs"),
        "tts_cache_dir": str(tmp_path / "audio"),
        "stock_media_cache_dir": str(tmp_path / "media"),
        "render_output_dir": str(tmp_path / "renders"),
        "llm_provider": "mock",
        "tts_provider": "mock",
        "stock_media_provider": "mock",
        "video_renderer": "mock",
        "automation_mode": "mock",
        "script_categories_csv": "horror,mystery",
        "story_categories_csv": "horror,mystery",
    }
    values.update(overrides)
    return Settings(**values)


def test_dashboard_renders_and_approve_reject_actions(monkeypatch, tmp_path):
    get_settings.cache_clear()
    db_file = tmp_path / "dashboard.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("AUTOMATION_MODE", "mock")
    monkeypatch.setenv("WORKFLOW_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("DASHBOARD_REQUIRE_TOKEN", "false")

    with TestClient(app) as client:
        run = client.post("/ops/run/daily-draft", json={"mock": True})
        draft_id = run.json()["created_script_id"]
        page = client.get("/dashboard")
        detail = client.get(f"/dashboard/scripts/{draft_id}")
        approved = client.post(
            f"/dashboard/scripts/{draft_id}/approve",
            follow_redirects=False,
        )
        rejected = client.post(
            f"/dashboard/scripts/{draft_id}/reject",
            data={"reason": "Needs a sharper ending."},
            follow_redirects=False,
        )
        shown = client.get(f"/scripts/{draft_id}")

    assert page.status_code == 200
    assert "RaatVerse Review Console" in page.text
    assert detail.status_code == 200
    assert approved.status_code == 303
    assert rejected.status_code == 303
    assert shown.json()["status"] == "rejected"
    assert shown.json()["rejection_reason"] == "Needs a sharper ending."
    get_settings.cache_clear()


def test_dashboard_token_requirement(monkeypatch, tmp_path):
    get_settings.cache_clear()
    db_file = tmp_path / "dashboard-token.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("DASHBOARD_REQUIRE_TOKEN", "true")
    monkeypatch.setenv("DASHBOARD_ADMIN_TOKEN", "secret-token")

    with TestClient(app) as client:
        blocked = client.get("/dashboard")
        allowed = client.get("/dashboard?token=secret-token")
        run = client.post("/ops/run/daily-draft", json={"mock": True})
        draft_id = run.json()["created_script_id"]
        action_blocked = client.post(
            f"/dashboard/scripts/{draft_id}/approve",
            follow_redirects=False,
        )
        action_allowed = client.post(
            f"/dashboard/scripts/{draft_id}/approve?token=secret-token",
            follow_redirects=False,
        )

    assert blocked.status_code == 403
    assert allowed.status_code == 200
    assert action_blocked.status_code == 403
    assert action_allowed.status_code == 303
    get_settings.cache_clear()


def test_db_backup_export_import_restore(tmp_path):
    settings = _settings(tmp_path)
    initialize_database(settings.database_url)
    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        WorkflowOrchestrationService(settings=settings, repository=repository).run_daily_draft(
            WorkflowRequest(mock=True)
        )

    backup = backup_database(settings)
    export = export_database_json(settings)
    backups = list_backups(settings)

    assert backup.exists()
    assert export.exists()
    assert backup in backups
    payload = json.loads(export.read_text(encoding="utf-8"))
    assert payload["schema"] == "raatverse-json-export-v1"
    assert payload["tables"]["script_drafts"]

    imported_settings = _settings(
        tmp_path,
        database_url=f"sqlite:///{(tmp_path / 'imported.db').as_posix()}",
    )
    imported = import_database_json(imported_settings, str(export))
    assert imported["script_drafts"] == 1

    with pytest.raises(PersistenceError):
        import_database_json(imported_settings, str(export))

    restored = restore_database(settings, str(backup))
    assert restored.exists()


def test_cli_db_and_notify_commands(tmp_path):
    db_file = tmp_path / "cli-phase8.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_file.as_posix()}",
        "DB_BACKUP_DIR": str(tmp_path / "backups"),
        "DB_EXPORT_DIR": str(tmp_path / "exports"),
        "LLM_PROVIDER": "mock",
        "AUTOMATION_MODE": "mock",
        "WORKFLOW_LOG_DIR": str(tmp_path / "logs"),
    }
    base = [sys.executable, "-m", "raatverse_agent"]

    subprocess.run([*base, "db", "init"], check=True, env=env)
    subprocess.run([*base, "workflow", "daily-draft", "--mock"], check=True, env=env)
    backup = subprocess.run([*base, "db", "backup"], check=True, env=env, capture_output=True, text=True)
    backups = subprocess.run([*base, "db", "backups"], check=True, env=env, capture_output=True, text=True)
    export = subprocess.run([*base, "db", "export-json"], check=True, env=env, capture_output=True, text=True)
    status = subprocess.run([*base, "db", "status"], check=True, env=env, capture_output=True, text=True)
    notify = subprocess.run([*base, "notify", "test", "--mock"], check=True, env=env, capture_output=True, text=True)

    assert "backup created" in backup.stdout.lower()
    assert ".sqlite3" in backups.stdout
    assert "json export created" in export.stdout.lower()
    assert "script_drafts" in status.stdout
    assert "Mock notification accepted" in notify.stdout


def test_sqlite_default_and_postgres_config_does_not_break_sqlite(tmp_path):
    default = Settings()
    mixed = _settings(tmp_path, db_engine="postgres")

    assert default.db_engine == "sqlite"
    assert default.database_url.startswith("sqlite")
    initialize_database(mixed.database_url)


def test_notifications_mock_and_webhook_missing_url(tmp_path):
    mock_settings = _settings(tmp_path, notifications_enabled=True, notification_provider="mock")
    result = NotificationService(mock_settings).event(
        event="test",
        title="Test",
        body="Body",
        mock=True,
        force=True,
    )

    assert result.sent is True
    assert result.provider == "mock"

    webhook_settings = _settings(
        tmp_path,
        notifications_enabled=True,
        notification_provider="webhook",
        notification_webhook_url="",
    )
    with pytest.raises(NotificationError):
        NotificationService(webhook_settings).event(
            event="test",
            title="Test",
            body="Body",
            force=True,
        )


def test_review_queue_grouping_includes_rejected_and_failed_workflows(tmp_path):
    settings = _settings(tmp_path)
    initialize_database(settings.database_url)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = WorkflowOrchestrationService(settings=settings, repository=repository)
        run = service.run_daily_draft(WorkflowRequest(mock=True))
        repository.update_script_draft_status(run.created_script_id, "rejected", "Not strong enough.")
        repository.update_workflow_run(run.id, WorkflowRunUpdate(status="failed"))
        queue = service.review_queue()

    assert queue.rejected_scripts
    assert queue.failed_workflows
    assert queue.total_pending >= 2


def test_github_artifact_workflows_remain_safe():
    daily = Path(".github/workflows/daily-draft.yml").read_text(encoding="utf-8")
    analytics = Path(".github/workflows/analytics-sync.yml").read_text(encoding="utf-8")

    assert "actions/upload-artifact@v4" in daily
    assert "actions/upload-artifact@v4" in analytics
    assert "retention-days: 7" in daily
    assert "AUTO_UPLOAD: \"false\"" in daily
    assert "AUTO_UPLOAD: \"false\"" in analytics
    assert "youtube upload" not in daily.lower()
