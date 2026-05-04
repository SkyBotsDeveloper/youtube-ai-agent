from fastapi.testclient import TestClient

from raatverse_agent.api.main import app
from raatverse_agent.config import get_settings


def test_youtube_api_mock_upload_workflow(monkeypatch, tmp_path):
    get_settings.cache_clear()
    db_file = tmp_path / "youtube-api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("TTS_PROVIDER", "mock")
    monkeypatch.setenv("STOCK_MEDIA_PROVIDER", "mock")
    monkeypatch.setenv("VIDEO_RENDERER", "mock")
    monkeypatch.setenv("TTS_CACHE_DIR", str(tmp_path / "audio"))
    monkeypatch.setenv("STOCK_MEDIA_CACHE_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("RENDER_OUTPUT_DIR", str(tmp_path / "renders"))
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "client-id")
    monkeypatch.setenv("YOUTUBE_TOKEN_FILE", str(tmp_path / "secrets" / "youtube_token.json"))

    with TestClient(app) as client:
        generated = client.post("/scripts/generate", json={"category": "horror", "mock": True})
        draft_id = generated.json()["saved_draft_id"]
        client.post(f"/scripts/{draft_id}/approve")
        prepared_assets = client.post(f"/assets/prepare/{draft_id}", json={"mock": True})
        asset_plan_id = prepared_assets.json()["id"]
        rendered = client.post(f"/renders/create/{asset_plan_id}", json={"mock": True})
        render_id = rendered.json()["id"]
        metadata = client.get(f"/youtube/metadata-preview/{render_id}")
        upload = client.post(f"/youtube/prepare-upload/{render_id}")
        upload_id = upload.json()["id"]
        approved = client.post(f"/youtube/approve-upload/{upload_id}")
        uploaded = client.post(f"/youtube/upload/{upload_id}", json={"mock": True})
        listed = client.get("/youtube/uploads")
        shown = client.get(f"/youtube/uploads/{upload_id}")
        oauth_url = client.get("/youtube/oauth-url")
        token_status = client.get("/youtube/token-status")

    assert metadata.status_code == 200
    assert metadata.json()["privacy_status"] == "private"
    assert upload.status_code == 200
    assert upload.json()["status"] == "upload_pending"
    assert approved.json()["status"] == "upload_approved"
    assert uploaded.json()["status"] == "upload_private"
    assert listed.status_code == 200
    assert len(listed.json()["uploads"]) == 1
    assert shown.json()["id"] == upload_id
    assert oauth_url.status_code == 200
    assert "accounts.google.com" in oauth_url.json()["authorization_url"]
    assert token_status.status_code == 200

    get_settings.cache_clear()
