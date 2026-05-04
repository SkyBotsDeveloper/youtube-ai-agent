from fastapi.testclient import TestClient

from raatverse_agent.api.main import app
from raatverse_agent.config import get_settings


def test_script_api_generate_list_show_approve_reject_and_revise(monkeypatch, tmp_path):
    get_settings.cache_clear()
    db_file = tmp_path / "script-api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("SCRIPT_CATEGORIES_CSV", "horror,mystery")

    with TestClient(app) as client:
        generated = client.post(
            "/scripts/generate",
            json={"category": "horror", "mock": True},
        )
        draft_id = generated.json()["saved_draft_id"]
        listed = client.get("/scripts")
        shown = client.get(f"/scripts/{draft_id}")
        approved = client.post(f"/scripts/{draft_id}/approve")
        rejected = client.post(
            f"/scripts/{draft_id}/reject",
            json={"reason": "Needs a sharper reveal."},
        )
        revised = client.post(
            f"/scripts/{draft_id}/revise",
            json={"reason": "Rewrite with a stronger opening hook."},
        )

    assert generated.status_code == 200
    assert generated.json()["draft"]["status"] == "draft"
    assert listed.status_code == 200
    assert len(listed.json()["scripts"]) == 1
    assert shown.status_code == 200
    assert approved.json()["status"] == "approved"
    assert rejected.json()["status"] == "rejected"
    assert revised.json()["status"] == "needs_revision"

    get_settings.cache_clear()


def test_script_api_real_provider_without_key_returns_clear_error(monkeypatch, tmp_path):
    get_settings.cache_clear()
    db_file = tmp_path / "script-api-no-key.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "gemini-test")

    with TestClient(app) as client:
        response = client.post(
            "/scripts/generate",
            json={"category": "horror", "mock": False},
        )

    assert response.status_code == 400
    assert "LLM_API_KEY" in response.json()["detail"]

    get_settings.cache_clear()
