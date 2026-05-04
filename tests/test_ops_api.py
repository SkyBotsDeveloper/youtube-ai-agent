from fastapi.testclient import TestClient

from raatverse_agent.api.main import app
from raatverse_agent.config import get_settings


def test_ops_api_and_dashboard(monkeypatch, tmp_path):
    get_settings.cache_clear()
    db_file = tmp_path / "ops-api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("TTS_PROVIDER", "mock")
    monkeypatch.setenv("STOCK_MEDIA_PROVIDER", "mock")
    monkeypatch.setenv("VIDEO_RENDERER", "mock")
    monkeypatch.setenv("AUTOMATION_MODE", "mock")
    monkeypatch.setenv("WORKFLOW_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("TTS_CACHE_DIR", str(tmp_path / "audio"))
    monkeypatch.setenv("STOCK_MEDIA_CACHE_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("RENDER_OUTPUT_DIR", str(tmp_path / "renders"))

    with TestClient(app) as client:
        health = client.get("/ops/health")
        run = client.post("/ops/run/daily-draft", json={"mock": True})
        run_id = run.json()["id"]
        status = client.get("/ops/status")
        runs = client.get("/ops/workflow-runs")
        shown = client.get(f"/ops/workflow-runs/{run_id}")
        queue = client.get("/review/queue")
        pending = client.get("/ops/pending-review")
        analytics_due = client.post("/ops/run/analytics-due", json={"mock": True})
        dashboard = client.get("/dashboard")

    assert health.status_code == 200
    assert health.json()["auto_upload"] is False
    assert run.status_code == 200
    assert run.json()["workflow_type"] == "daily_draft"
    assert run.json()["status"] == "success"
    assert status.status_code == 200
    assert status.json()["auto_upload"] is False
    assert runs.status_code == 200
    assert len(runs.json()["workflow_runs"]) >= 1
    assert shown.json()["id"] == run_id
    assert queue.status_code == 200
    assert queue.json()["pending_script_drafts"]
    assert pending.status_code == 200
    assert analytics_due.status_code == 200
    assert analytics_due.json()["workflow_type"] == "analytics_sync"
    assert dashboard.status_code == 200
    assert "RaatVerse Operations" in dashboard.text

    get_settings.cache_clear()
