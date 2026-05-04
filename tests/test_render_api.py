from fastapi.testclient import TestClient

from raatverse_agent.api.main import app
from raatverse_agent.config import get_settings


def test_render_api_validate_create_list_show(monkeypatch, tmp_path):
    get_settings.cache_clear()
    db_file = tmp_path / "render-api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("TTS_PROVIDER", "mock")
    monkeypatch.setenv("STOCK_MEDIA_PROVIDER", "mock")
    monkeypatch.setenv("VIDEO_RENDERER", "mock")
    monkeypatch.setenv("TTS_CACHE_DIR", str(tmp_path / "audio"))
    monkeypatch.setenv("STOCK_MEDIA_CACHE_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("RENDER_OUTPUT_DIR", str(tmp_path / "renders"))

    with TestClient(app) as client:
        generated = client.post("/scripts/generate", json={"category": "horror", "mock": True})
        draft_id = generated.json()["saved_draft_id"]
        client.post(f"/scripts/{draft_id}/approve")
        prepared = client.post(f"/assets/prepare/{draft_id}", json={"mock": True})
        asset_plan_id = prepared.json()["id"]
        validation = client.post(f"/renders/validate/{asset_plan_id}", json={"mock": True})
        created = client.post(f"/renders/create/{asset_plan_id}", json={"mock": True})
        render_id = created.json()["id"]
        listed = client.get("/renders")
        shown = client.get(f"/renders/{render_id}")

    assert validation.status_code == 200
    assert validation.json()["is_valid"] is True
    assert created.status_code == 200
    assert created.json()["status"] == "render_ready"
    assert listed.status_code == 200
    assert len(listed.json()["renders"]) == 1
    assert shown.status_code == 200
    assert shown.json()["id"] == render_id

    get_settings.cache_clear()
