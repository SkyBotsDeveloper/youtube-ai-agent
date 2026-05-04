from __future__ import annotations

from raatverse_agent.youtube.models import OAuthTokenStatus, YouTubeMetadata, YouTubeUpload


def format_metadata_preview(metadata: YouTubeMetadata) -> str:
    tags = ", ".join(metadata.tags)
    return (
        "RaatVerse YouTube metadata preview\n"
        f"Title: {metadata.title}\n"
        f"Privacy: {metadata.privacy_status}\n"
        f"Category ID: {metadata.category_id}\n"
        f"Made for kids: {metadata.self_declared_made_for_kids}\n"
        f"Contains synthetic media: {metadata.contains_synthetic_media}\n"
        f"Scheduled publish: {metadata.scheduled_publish_at or 'None'}\n"
        f"Tags: {tags}\n"
        "Description:\n"
        f"{metadata.description}"
    )


def format_youtube_upload(upload: YouTubeUpload) -> str:
    return (
        "RaatVerse YouTube upload record\n"
        f"Upload ID: {upload.id}\n"
        f"Render ID: {upload.video_render_id}\n"
        f"Script draft ID: {upload.script_draft_id}\n"
        f"Asset plan ID: {upload.asset_plan_id}\n"
        f"Status: {upload.status}\n"
        f"Provider: {upload.upload_provider}\n"
        f"Privacy: {upload.privacy_status}\n"
        f"Scheduled publish: {upload.scheduled_publish_at or 'None'}\n"
        f"YouTube video ID: {upload.youtube_video_id or 'None'}\n"
        f"YouTube URL: {upload.youtube_url or 'None'}\n"
        f"Title: {upload.title}\n"
        f"Category ID: {upload.category_id}\n"
        f"Made for kids: {upload.self_declared_made_for_kids}\n"
        f"Contains synthetic media: {upload.contains_synthetic_media}\n"
        f"Error: {upload.error_message or 'None'}"
    )


def format_token_status(status: OAuthTokenStatus) -> str:
    return (
        "RaatVerse YouTube OAuth token status\n"
        f"Has client ID: {status.has_client_id}\n"
        f"Has client secret: {status.has_client_secret}\n"
        f"Has env refresh token: {status.has_env_refresh_token}\n"
        f"Token file: {status.token_file_path}\n"
        f"Token file exists: {status.token_file_exists}\n"
        f"Has file refresh token: {status.has_file_refresh_token}\n"
        f"Has file access token: {status.has_file_access_token}\n"
        f"Access token expires at: {status.access_token_expires_at or 'None'}\n"
        f"Configured scopes: {', '.join(status.configured_scopes) or 'None'}\n"
        f"Token scopes: {', '.join(status.token_scopes) or 'None'}\n"
        f"Has analytics scope: {status.has_analytics_scope}"
    )
