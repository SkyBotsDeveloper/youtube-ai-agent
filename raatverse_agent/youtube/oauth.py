from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx

from raatverse_agent.config import Settings
from raatverse_agent.youtube.models import OAuthTokenStatus

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


class YouTubeOAuthError(RuntimeError):
    pass


def build_oauth_url(settings: Settings, *, state: str | None = None) -> str:
    if not settings.youtube_client_id:
        raise YouTubeOAuthError("YOUTUBE_CLIENT_ID is required to build an OAuth URL.")
    if not settings.youtube_redirect_uri:
        raise YouTubeOAuthError("YOUTUBE_REDIRECT_URI is required to build an OAuth URL.")

    params = {
        "client_id": settings.youtube_client_id,
        "redirect_uri": settings.youtube_redirect_uri,
        "response_type": "code",
        "scope": settings.youtube_scopes,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    if state:
        params["state"] = state
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_token(settings: Settings, code: str) -> dict:
    _require_oauth_credentials(settings)
    response = httpx.post(
        settings.youtube_token_uri,
        data={
            "code": code,
            "client_id": settings.youtube_client_id,
            "client_secret": settings.youtube_client_secret,
            "redirect_uri": settings.youtube_redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=20,
    )
    if response.status_code >= 400:
        raise YouTubeOAuthError(
            f"OAuth token exchange failed with HTTP {response.status_code}: {response.text[:500]}"
        )
    token = _with_expires_at(response.json())
    save_token_file(settings, token)
    return token


def get_access_token(settings: Settings) -> str:
    token = load_token_file(settings)
    if token and token.get("access_token") and _access_token_is_fresh(token):
        return str(token["access_token"])

    refresh_token = settings.youtube_refresh_token or (token or {}).get("refresh_token")
    if not refresh_token:
        raise YouTubeOAuthError(
            "No YouTube refresh token found. Run youtube oauth-url and exchange-code, "
            "or set YOUTUBE_REFRESH_TOKEN."
        )

    _require_oauth_credentials(settings)
    response = httpx.post(
        settings.youtube_token_uri,
        data={
            "client_id": settings.youtube_client_id,
            "client_secret": settings.youtube_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=20,
    )
    if response.status_code >= 400:
        raise YouTubeOAuthError(
            f"OAuth token refresh failed with HTTP {response.status_code}: {response.text[:500]}"
        )

    refreshed = _with_expires_at(response.json())
    refreshed["refresh_token"] = refresh_token
    save_token_file(settings, refreshed)
    return str(refreshed["access_token"])


def token_status(settings: Settings) -> OAuthTokenStatus:
    token = load_token_file(settings)
    configured_scopes = list(settings.youtube_scope_list)
    token_scopes = str((token or {}).get("scope", "")).split()
    scope_source = set(token_scopes or configured_scopes)
    analytics_scopes = {
        "https://www.googleapis.com/auth/yt-analytics.readonly",
        "https://www.googleapis.com/auth/youtube.readonly",
    }
    return OAuthTokenStatus(
        has_client_id=bool(settings.youtube_client_id),
        has_client_secret=bool(settings.youtube_client_secret),
        has_env_refresh_token=bool(settings.youtube_refresh_token),
        token_file_path=settings.youtube_token_file,
        token_file_exists=Path(settings.youtube_token_file).exists(),
        has_file_refresh_token=bool((token or {}).get("refresh_token")),
        has_file_access_token=bool((token or {}).get("access_token")),
        access_token_expires_at=(token or {}).get("expires_at"),
        configured_scopes=configured_scopes,
        token_scopes=token_scopes,
        has_analytics_scope=analytics_scopes.issubset(scope_source),
    )


def revoke_local_token(settings: Settings) -> bool:
    path = Path(settings.youtube_token_file)
    if not path.exists():
        return False
    path.unlink()
    return True


def load_token_file(settings: Settings) -> dict | None:
    path = Path(settings.youtube_token_file)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise YouTubeOAuthError(f"YouTube token file is malformed: {path}") from exc


def save_token_file(settings: Settings, token: dict) -> Path:
    path = Path(settings.youtube_token_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(token, indent=2), encoding="utf-8")
    return path


def _with_expires_at(token: dict) -> dict:
    expires_in = int(token.get("expires_in", 3600))
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return {**token, "expires_at": expires_at.isoformat()}


def _access_token_is_fresh(token: dict) -> bool:
    expires_at = token.get("expires_at")
    if not expires_at:
        return False
    parsed = datetime.fromisoformat(str(expires_at))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed > datetime.now(timezone.utc) + timedelta(seconds=90)


def _require_oauth_credentials(settings: Settings) -> None:
    missing = []
    if not settings.youtube_client_id:
        missing.append("YOUTUBE_CLIENT_ID")
    if not settings.youtube_client_secret:
        missing.append("YOUTUBE_CLIENT_SECRET")
    if not settings.youtube_redirect_uri:
        missing.append("YOUTUBE_REDIRECT_URI")
    if missing:
        raise YouTubeOAuthError(f"Missing YouTube OAuth settings: {', '.join(missing)}")
