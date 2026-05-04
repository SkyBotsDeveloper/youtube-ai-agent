from __future__ import annotations

from datetime import timezone
from pathlib import Path
from uuid import uuid4

import httpx

from raatverse_agent.config import Settings
from raatverse_agent.rendering.models import VideoRender
from raatverse_agent.youtube.models import YouTubeUpload, YouTubeUploadResult
from raatverse_agent.youtube.oauth import YouTubeOAuthError, get_access_token

YOUTUBE_RESUMABLE_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


class YouTubeUploadError(RuntimeError):
    pass


class MockYouTubeUploader:
    def __init__(self, settings: Settings):
        self.settings = settings

    def upload(self, upload: YouTubeUpload, render: VideoRender) -> YouTubeUploadResult:
        video_id = f"mock-{uuid4().hex[:12]}"
        status = "upload_scheduled" if upload.scheduled_publish_at else "upload_private"
        return YouTubeUploadResult(
            youtube_video_id=video_id,
            youtube_url=f"https://www.youtube.com/watch?v={video_id}",
            status=status,  # type: ignore[arg-type]
        )


class YouTubeDataApiUploader:
    def __init__(self, settings: Settings):
        self.settings = settings

    def upload(self, upload: YouTubeUpload, render: VideoRender) -> YouTubeUploadResult:
        output_path = Path(render.output_path or "")
        if not output_path.exists():
            raise YouTubeUploadError(f"Render output file does not exist: {output_path}")

        try:
            access_token = get_access_token(self.settings)
        except YouTubeOAuthError as exc:
            raise YouTubeUploadError(str(exc)) from exc

        body = self._build_video_resource(upload)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(output_path.stat().st_size),
        }
        params = {"uploadType": "resumable", "part": "snippet,status"}

        try:
            with httpx.Client(timeout=60) as client:
                init = client.post(
                    YOUTUBE_RESUMABLE_UPLOAD_URL,
                    params=params,
                    headers=headers,
                    json=body,
                )
                if init.status_code >= 400:
                    raise YouTubeUploadError(
                        f"YouTube upload session failed with HTTP {init.status_code}: {init.text[:700]}"
                    )
                upload_url = init.headers.get("Location")
                if not upload_url:
                    raise YouTubeUploadError("YouTube upload session did not return a resumable Location header.")

                with output_path.open("rb") as video_file:
                    put = client.put(
                        upload_url,
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "video/mp4",
                        },
                        content=video_file.read(),
                    )
                if put.status_code >= 400:
                    raise YouTubeUploadError(
                        f"YouTube video upload failed with HTTP {put.status_code}: {put.text[:700]}"
                    )
        except httpx.HTTPError as exc:
            raise YouTubeUploadError(f"YouTube upload request failed: {exc}") from exc

        payload = put.json()
        video_id = payload.get("id")
        if not video_id:
            raise YouTubeUploadError("YouTube upload response did not include a video id.")
        status = "upload_scheduled" if upload.scheduled_publish_at else "upload_private"
        return YouTubeUploadResult(
            youtube_video_id=video_id,
            youtube_url=f"https://www.youtube.com/watch?v={video_id}",
            status=status,  # type: ignore[arg-type]
        )

    def _build_video_resource(self, upload: YouTubeUpload) -> dict:
        privacy_status = "private"
        status = {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": upload.self_declared_made_for_kids,
            "containsSyntheticMedia": upload.contains_synthetic_media,
        }
        if upload.scheduled_publish_at:
            publish_at = upload.scheduled_publish_at.astimezone(timezone.utc)
            status["publishAt"] = publish_at.isoformat().replace("+00:00", "Z")

        return {
            "snippet": {
                "title": upload.title,
                "description": upload.description,
                "tags": upload.tags,
                "categoryId": upload.category_id,
                "defaultLanguage": self.settings.youtube_default_language,
            },
            "status": status,
        }


def create_youtube_uploader(settings: Settings, *, mock: bool = False):
    if mock:
        return MockYouTubeUploader(settings)
    return YouTubeDataApiUploader(settings)
