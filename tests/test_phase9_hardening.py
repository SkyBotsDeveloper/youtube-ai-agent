import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from raatverse_agent.api.main import app
from raatverse_agent.config import Settings, get_settings
from raatverse_agent.db.migrations import upgrade_database
from raatverse_agent.db.repositories import RaatVerseRepository
from raatverse_agent.db.session import initialize_database, session_scope
from raatverse_agent.ops.health import ops_health_payload
from raatverse_agent.ops.workflow import WorkflowOrchestrationService


def _settings(tmp_path, **overrides):
    values = {
        "database_url": f"sqlite:///{(tmp_path / 'phase9.db').as_posix()}",
        "db_backup_dir": str(tmp_path / "backups"),
        "db_export_dir": str(tmp_path / "exports"),
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


def test_alembic_upgrade_works_with_sqlite(tmp_path):
    settings = _settings(tmp_path)
    upgrade_database(settings)
    initialize_database(settings.database_url)

    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        tables = {row[0] for row in session.execute(text("select name from sqlite_master where type='table'"))}
        repository.create_audit_log(
            actor="test",
            action="migration_verified",
            entity_type="database",
        )

    assert "alembic_version" in tables
    assert "audit_logs" in tables


def test_db_migration_cli_helpers(tmp_path):
    db_file = tmp_path / "cli-migrate.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_file.as_posix()}",
        "LLM_PROVIDER": "mock",
    }
    base = [sys.executable, "-m", "raatverse_agent"]

    upgraded = subprocess.run([*base, "db", "upgrade"], check=True, env=env, capture_output=True, text=True)
    current = subprocess.run([*base, "db", "current"], check=True, env=env, capture_output=True, text=True)
    history = subprocess.run([*base, "db", "history"], check=True, env=env, capture_output=True, text=True)

    assert "upgraded to head" in upgraded.stdout.lower()
    assert "0004_render_timing_report" in current.stdout
    assert "Initial RaatVerse schema" in history.stdout


def test_dashboard_actions_create_audit_logs(monkeypatch, tmp_path):
    get_settings.cache_clear()
    db_file = tmp_path / "dashboard-audit.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("AUTOMATION_MODE", "mock")
    monkeypatch.setenv("AUDIT_LOG_ENABLED", "true")

    with TestClient(app) as client:
        run = client.post("/ops/run/daily-draft", json={"mock": True})
        draft_id = run.json()["created_script_id"]
        approved = client.post(f"/dashboard/scripts/{draft_id}/approve", follow_redirects=False)
        logs = client.get("/audit/logs?action=script_approve")
        log_detail = client.get(f"/audit/logs/{logs.json()['audit_logs'][0]['id']}")

    assert approved.status_code == 303
    assert logs.status_code == 200
    assert logs.json()["audit_logs"][0]["entity_id"] == draft_id
    assert log_detail.json()["action"] == "script_approve"
    get_settings.cache_clear()


def test_dashboard_read_protection_and_filtering(monkeypatch, tmp_path):
    get_settings.cache_clear()
    db_file = tmp_path / "dashboard-protected.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("AUTOMATION_MODE", "mock")
    monkeypatch.setenv("DASHBOARD_REQUIRE_TOKEN", "false")
    monkeypatch.setenv("DASHBOARD_PROTECT_READS", "true")
    monkeypatch.setenv("DASHBOARD_ADMIN_TOKEN", "read-token")

    with TestClient(app) as client:
        run = client.post("/ops/run/daily-draft", json={"mock": True})
        title = client.get(f"/scripts/{run.json()['created_script_id']}").json()["title"]
        blocked = client.get("/dashboard")
        allowed = client.get("/dashboard?token=read-token&q=Aakhri")

    assert blocked.status_code == 403
    assert allowed.status_code == 200
    assert title in allowed.text
    get_settings.cache_clear()


def test_ops_health_endpoint_and_doctor_warnings(monkeypatch, tmp_path):
    get_settings.cache_clear()
    db_file = tmp_path / "ops-health.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))

    with TestClient(app) as client:
        health = client.get("/ops/health")

    assert health.status_code == 200
    assert health.json()["db"]["ok"] is True
    assert health.json()["auto_upload"] is False

    settings = _settings(tmp_path, auto_upload=True, confirm_enable_auto_upload=False)
    initialize_database(settings.database_url)
    with session_scope(settings.database_url) as session:
        repository = RaatVerseRepository(session)
        service = WorkflowOrchestrationService(settings=settings, repository=repository)
        payload = ops_health_payload(
            settings=settings,
            queue=service.review_queue(),
            latest_workflow_run=None,
        )

    assert any("AUTO_UPLOAD" in warning for warning in payload["warnings"])
    get_settings.cache_clear()


def test_audit_and_ops_cli_commands(tmp_path):
    db_file = tmp_path / "cli-audit.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_file.as_posix()}",
        "LLM_PROVIDER": "mock",
        "AUTOMATION_MODE": "mock",
        "OUTPUT_DIR": str(tmp_path / "outputs"),
    }
    base = [sys.executable, "-m", "raatverse_agent"]

    subprocess.run([*base, "db", "init"], check=True, env=env)
    subprocess.run([*base, "workflow", "daily-draft", "--mock"], check=True, env=env)
    audit = subprocess.run([*base, "audit", "list"], check=True, env=env, capture_output=True, text=True)
    health = subprocess.run([*base, "ops", "health"], check=True, env=env, capture_output=True, text=True)
    doctor = subprocess.run([*base, "ops", "doctor"], check=True, env=env, capture_output=True, text=True)

    assert "workflow_run_triggered" in audit.stdout
    assert "operations health" in health.stdout.lower()
    assert "ops doctor" in doctor.stdout.lower()


def test_phase9_config_safety_warnings(tmp_path):
    auto_upload = _settings(tmp_path, auto_upload=True, confirm_enable_auto_upload=False)
    protected_dashboard = _settings(tmp_path, dashboard_require_token=True, dashboard_admin_token="")
    production_sqlite = _settings(tmp_path, app_env="production")

    assert any("AUTO_UPLOAD" in warning for warning in auto_upload.safety_warnings)
    assert any("DASHBOARD_ADMIN_TOKEN" in warning for warning in protected_dashboard.safety_warnings)
    assert any("Production mode is using SQLite" in warning for warning in production_sqlite.safety_warnings)


def test_deployment_files_exist_and_are_safe():
    files = [
        Path("docker-compose.prod.yml"),
        Path("Caddyfile.example"),
        Path("render.yaml"),
        Path("railway.json"),
        Path("scripts/deploy_vps.sh"),
        Path("scripts/backup_cron.sh"),
        Path("scripts/restore_from_backup.sh"),
    ]

    for path in files:
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "AUTO_UPLOAD" not in text or "false" in text
        assert "your-domain.example" in text or "raatverse" in text.lower() or path.suffix == ".json"
        assert "real-secret" not in text.lower()
