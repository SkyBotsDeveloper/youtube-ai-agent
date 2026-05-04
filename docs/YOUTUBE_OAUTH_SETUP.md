# YouTube OAuth Setup

Real uploads require OAuth authorization for the YouTube Data API v3 upload scope. Real analytics requires YouTube Analytics API access and read-only scopes.

## Google Cloud Console

1. Create or select a Google Cloud project.
2. Enable **YouTube Data API v3**.
3. Enable **YouTube Analytics API** for Phase 6 analytics.
4. Configure the OAuth consent screen.
5. Create an OAuth Client ID.
6. Choose an app type that matches your local flow.
7. Add the redirect URI from `.env`, for example:

```text
http://localhost:8080/oauth2callback
```

8. Copy the client ID and client secret into your local `.env`.

## Environment

```env
YOUTUBE_CLIENT_ID=replace-with-youtube-oauth-client-id
YOUTUBE_CLIENT_SECRET=replace-with-youtube-oauth-client-secret
YOUTUBE_REDIRECT_URI=http://localhost:8080/oauth2callback
YOUTUBE_TOKEN_FILE=./secrets/youtube_token.json
YOUTUBE_SCOPES=https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/yt-analytics.readonly https://www.googleapis.com/auth/youtube.readonly
```

`yt-analytics.readonly` grants read-only YouTube Analytics access. Current Google `reports.query` documentation also requires `youtube.readonly`, so both read-only scopes are included alongside the existing upload scope.

If you already created a token before Phase 6, re-authorize after changing `YOUTUBE_SCOPES`:

```bash
python -m raatverse_agent youtube revoke-local-token
python -m raatverse_agent youtube oauth-url
python -m raatverse_agent youtube exchange-code <code>
python -m raatverse_agent youtube token-status
```

## Authorization Flow

Print the auth URL:

```bash
python -m raatverse_agent youtube oauth-url
```

Open the URL, approve access, then copy the `code` query parameter from the redirect URL.

Exchange the code:

```bash
python -m raatverse_agent youtube exchange-code <code>
```

Check token status:

```bash
python -m raatverse_agent youtube token-status
```

Delete the local token file:

```bash
python -m raatverse_agent youtube revoke-local-token
```

## Token Storage

Tokens are stored locally at `./secrets/youtube_token.json` by default. The `secrets/` directory and token JSON patterns are ignored by git. Do not commit OAuth tokens, refresh tokens, client secrets, or API keys.

You can also provide `YOUTUBE_REFRESH_TOKEN` through environment variables for env-only deployments.

## References

- YouTube Analytics API `reports.query`: https://developers.google.com/youtube/analytics/reference/reports/query
- YouTube Analytics metrics: https://developers.google.com/youtube/analytics/metrics
- Google OAuth web server flow: https://developers.google.com/identity/protocols/oauth2/web-server
