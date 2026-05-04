import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from raatverse_agent.api.main import app
from raatverse_agent.config import Settings, get_settings
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.db.session import initialize_database, session_scope
from raatverse_agent.ops.workflow import WorkflowOrchestrationService


def _settings(tmp_path, **overrides):
    values = {
        "database_url": f"sqlite:///{(tmp_path / 'phase10.db').as_posix()}",
        "db_backup_dir": str(tmp_path / "backups"),
        "db_export_dir": str(tmp_path / "exports"),
        "audit_export_dir": str(tmp_path / "audit_exports"),
        "workflow_log_dir": str(tmp_path / "logs"),
        "tts_cache_dir": str(tmp_path / "audio"),
        "stock_media_cache_dir": str(tmp_path / "media"),
        "render_output_dir": str(tmp_path / "renders"),
        "output_dir": str(tmp_path / "outputs"),
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


def test_release_status_and_checklist_cli(tmp_path):
    db_file = tmp_path / "release.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_file.as_posix()}",
        "DB_BACKUP_DIR": str(tmp_path / "backups"),
        "AUDIT_EXPORT_DIR": str(tmp_path / "audit_exports"),
        "LLM_PROVIDER": "mock",
    }
    base = [sys.executable, "-m", "raatverse_agent"]

    subprocess.run([*base, "db", "init"], check=True, env=env)
    status = subprocess.run([*base, "release", "status"], check=True, env=env, capture_output=True, text=True)
    checklist = subprocess.run([*base, "release", "checklist"], check=True, env=env, capture_output=True, text=True)
    notes = subprocess.run([*base, "release", "notes"], check=True, env=env, capture_output=True, text=True)

    assert "RaatVerse release status" in status.stdout
    assert "Run python -m raatverse_agent db safe-upgrade" in checklist.stdout
    assert "0.1.0" in notes.stdout


def test_db_safe_upgrade_creates_backup(tmp_path):
    db_file = tmp_path / "safe-upgrade.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_file.as_posix()}",
        "DB_BACKUP_DIR": str(tmp_path / "backups"),
        "LLM_PROVIDER": "mock",
    }
    base = [sys.executable, "-m", "raatverse_agent"]

    subprocess.run([*base, "db", "init"], check=True, env=env)
    result = subprocess.run([*base, "db", "safe-upgrade"], check=True, env=env, capture_output=True, text=True)

    assert "safe upgrade completed" in result.stdout.lower()
    assert list((tmp_path / "backups").glob("*.sqlite3"))


def test_dashboard_approval_comment_history(monkeypatch, tmp_path):
    get_settings.cache_clear()
    db_file = tmp_path / "approval-history.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("AUTOMATION_MODE", "mock")
    monkeypatch.setenv("AUDIT_LOG_ENABLED", "true")

    with TestClient(app) as client:
        run = client.post("/ops/run/daily-draft", json={"mock": True})
        draft_id = run.json()["created_script_id"]
        approved = client.post(
            f"/dashboard/scripts/{draft_id}/approve",
            data={"comment": "Approved for dark cinematic style."},
            follow_redirects=False,
        )
        detail = client.get(f"/dashboard/scripts/{draft_id}")
        audit = client.get("/audit/logs?action=script_approve")

    assert approved.status_code == 303
    assert "Approved for dark cinematic style." in detail.text
    assert audit.json()["audit_logs"][0]["reason"] == "Approved for dark cinematic style."
    get_settings.cache_clear()


def test_audit_export_json_csv_and_filters(tmp_path):
    settings = _settings(tmp_path)
    initialize_database(settings.database_url)
    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        repository.create_audit_log(actor="test", action="script_approve", entity_type="script_draft", entity_id=1)
        repository.create_audit_log(actor="test", action="render_create", entity_type="video_render", entity_id=2)

    env = {
        **os.environ,
        "DATABASE_URL": settings.database_url,
        "AUDIT_EXPORT_DIR": settings.audit_export_dir,
        "LLM_PROVIDER": "mock",
    }
    base = [sys.executable, "-m", "raatverse_agent"]
    exported = subprocess.run(
        [*base, "audit", "export-json", "--action", "script_approve"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    csv_exported = subprocess.run(
        [*base, "audit", "export-csv", "--entity-type", "video_render"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    json_files = list(Path(settings.audit_export_dir).glob("*.json"))
    csv_files = list(Path(settings.audit_export_dir).glob("*.csv"))
    payload = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert "Audit JSON export created" in exported.stdout
    assert "Audit CSV export created" in csv_exported.stdout
    assert payload["count"] == 1
    assert payload["audit_logs"][0]["action"] == "script_approve"
    assert csv_files


def test_audit_export_api(monkeypatch, tmp_path):
    get_settings.cache_clear()
    db_file = tmp_path / "audit-api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    with TestClient(app) as client:
        client.post("/ops/run/daily-draft", json={"mock": True})
        json_export = client.get("/audit/export.json?action=workflow_run_triggered")
        csv_export = client.get("/audit/export.csv?action=workflow_run_triggered")

    assert json_export.status_code == 200
    assert json_export.json()["schema"] == "raatverse-audit-export-v1"
    assert csv_export.status_code == 200
    assert "workflow_run_triggered" in csv_export.text
    get_settings.cache_clear()


def test_ops_doctor_production_warnings(tmp_path):
    settings = _settings(
        tmp_path,
        app_env="production",
        dashboard_require_token=False,
        dashboard_admin_token="",
        db_backup_before_upgrade=False,
        release_backup_required=False,
    )
    initialize_database(settings.database_url)
    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = WorkflowOrchestrationService(settings=settings, repository=repository)
        health = service.status()

    assert health.auto_upload is False
    assert any("DASHBOARD_REQUIRE_TOKEN" in warning for warning in settings.safety_warnings)


def test_ops_e2e_check_mock_cli(tmp_path):
    db_file = tmp_path / "e2e.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_file.as_posix()}",
        "DB_BACKUP_DIR": str(tmp_path / "backups"),
        "LLM_PROVIDER": "mock",
        "TTS_PROVIDER": "mock",
        "STOCK_MEDIA_PROVIDER": "mock",
        "VIDEO_RENDERER": "mock",
        "AUTOMATION_MODE": "mock",
        "OUTPUT_DIR": str(tmp_path / "outputs"),
    }
    base = [sys.executable, "-m", "raatverse_agent"]

    subprocess.run([*base, "db", "init"], check=True, env=env)
    result = subprocess.run([*base, "ops", "e2e-check", "--mock"], check=True, env=env, capture_output=True, text=True)

    assert "E2E mock check" in result.stdout
    assert "Full mock run" in result.stdout


def test_phase10_docs_and_deployment_files_are_safe():
    required = [
        "docs/RELEASE_OPERATIONS.md",
        "docs/UPGRADE_ROLLBACK.md",
        "docs/MIGRATION_DISCIPLINE.md",
        "docs/APPROVAL_HISTORY.md",
        "docs/AUDIT_EXPORT.md",
        "docs/PRODUCTION_CHECKLIST.md",
        "docs/DEPLOYMENT_VPS_DOCKER_CADDY.md",
        "docs/DEPLOYMENT_WINDOWS_LOCAL.md",
        "docs/E2E_DRY_RUN.md",
        "docs/REAL_API_SETUP_CHECKLIST.md",
        "docker-compose.prod.yml",
        "Caddyfile.example",
    ]

    for filename in required:
        path = Path(filename)
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "AUTO_UPLOAD=false" in text or "AUTO_UPLOAD" not in text or "false" in text
        assert "real-secret" not in text.lower()
