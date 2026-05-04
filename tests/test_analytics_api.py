from fastapi.testclient import TestClient

from raatverse_agent.api.main import app
from raatverse_agent.config import get_settings


def test_analytics_api_mock_workflow(monkeypatch, tmp_path):
    get_settings.cache_clear()
    db_file = tmp_path / "analytics-api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("TTS_PROVIDER", "mock")
    monkeypatch.setenv("STOCK_MEDIA_PROVIDER", "mock")
    monkeypatch.setenv("VIDEO_RENDERER", "mock")
    monkeypatch.setenv("TTS_CACHE_DIR", str(tmp_path / "audio"))
    monkeypatch.setenv("STOCK_MEDIA_CACHE_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("RENDER_OUTPUT_DIR", str(tmp_path / "renders"))
    monkeypatch.setenv("YOUTUBE_TOKEN_FILE", str(tmp_path / "secrets" / "youtube_token.json"))

    with TestClient(app) as client:
        generated = client.post("/scripts/generate", json={"category": "horror", "mock": True})
        draft_id = generated.json()["saved_draft_id"]
        client.post(f"/scripts/{draft_id}/approve")
        prepared_assets = client.post(f"/assets/prepare/{draft_id}", json={"mock": True})
        asset_plan_id = prepared_assets.json()["id"]
        rendered = client.post(f"/renders/create/{asset_plan_id}", json={"mock": True})
        render_id = rendered.json()["id"]
        upload = client.post(f"/youtube/prepare-upload/{render_id}")
        upload_id = upload.json()["id"]
        client.post(f"/youtube/approve-upload/{upload_id}")
        client.post(f"/youtube/upload/{upload_id}", json={"mock": True})

        fetched = client.post(f"/analytics/fetch/{upload_id}", json={"mock": True})
        snapshot_id = fetched.json()["id"]
        listed = client.get("/analytics/snapshots")
        shown = client.get(f"/analytics/snapshots/{snapshot_id}")
        scores = client.post("/analytics/update-scores")
        recommendation = client.get("/strategy/recommend")
        categories = client.get("/strategy/categories")

    assert fetched.status_code == 200
    assert fetched.json()["status"] == "snapshot_ready"
    assert fetched.json()["views"] > 0
    assert listed.status_code == 200
    assert len(listed.json()["snapshots"]) == 1
    assert shown.json()["id"] == snapshot_id
    assert scores.status_code == 200
    assert scores.json()["category_scores"][0]["category"] == "horror"
    assert recommendation.status_code == 200
    assert recommendation.json()["next_category"] == "horror"
    assert categories.status_code == 200

    get_settings.cache_clear()
