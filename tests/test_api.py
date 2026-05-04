from fastapi.testclient import TestClient

from raatverse_agent.api.main import app
from raatverse_agent.config import get_settings


def test_api_health_run_mock_and_list_runs(monkeypatch, tmp_path):
    get_settings.cache_clear()
    db_file = tmp_path / "api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("STORY_CATEGORIES_CSV", "haunted-room,train-mystery")

    with TestClient(app) as client:
        health = client.get("/health")
        run = client.post("/pipeline/run-mock")
        runs = client.get("/pipeline/runs")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert run.status_code == 200
    assert run.json()["status"] == "completed"
    assert runs.status_code == 200
    assert len(runs.json()["runs"]) == 1

    get_settings.cache_clear()
