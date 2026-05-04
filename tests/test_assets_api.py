from fastapi.testclient import TestClient

from raatverse_agent.api.main import app
from raatverse_agent.config import get_settings


def test_assets_api_tts_prepare_list_show_and_regenerate(monkeypatch, tmp_path):
    get_settings.cache_clear()
    db_file = tmp_path / "assets-api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("TTS_PROVIDER", "mock")
    monkeypatch.setenv("STOCK_MEDIA_PROVIDER", "mock")
    monkeypatch.setenv("TTS_CACHE_DIR", str(tmp_path / "audio"))
    monkeypatch.setenv("STOCK_MEDIA_CACHE_DIR", str(tmp_path / "media"))

    with TestClient(app) as client:
        generated = client.post("/scripts/generate", json={"category": "horror", "mock": True})
        draft_id = generated.json()["saved_draft_id"]
        approved = client.post(f"/scripts/{draft_id}/approve")
        audio = client.post(f"/tts/generate/{draft_id}", json={"mock": True})
        prepared = client.post(f"/assets/prepare/{draft_id}", json={"mock": True})
        listed = client.get("/assets")
        shown = client.get(f"/assets/{prepared.json()['id']}")
        rejected = client.post(
            f"/scripts/{draft_id}/reject",
            json={"reason": "Need a stronger ending."},
        )
        regenerated = client.post(f"/scripts/{draft_id}/regenerate", json={"mock": True})

    assert approved.status_code == 200
    assert audio.status_code == 200
    assert audio.json()["status"] == "asset_ready"
    assert prepared.status_code == 200
    assert prepared.json()["status"] == "asset_ready"
    assert listed.status_code == 200
    assert len(listed.json()["asset_plans"]) == 1
    assert shown.status_code == 200
    assert rejected.status_code == 200
    assert regenerated.status_code == 200
    assert regenerated.json()["saved_draft_id"] != draft_id

    get_settings.cache_clear()
