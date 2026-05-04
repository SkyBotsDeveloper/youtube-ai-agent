# YouTube Analytics

Phase 6 adds official YouTube Analytics API support plus an offline mock analytics provider.

## Mock Workflow

Mock mode requires no Google credentials and does not call external services:

```bash
python -m raatverse_agent analytics fetch 1 --mock
python -m raatverse_agent analytics update-scores
python -m raatverse_agent analytics list
python -m raatverse_agent strategy recommend
```

The mock fetcher creates realistic fake values for views, likes, comments, shares, watch time, average view duration, subscriber gain/loss, and stores them in `analytics_snapshots`.

## Real Workflow

Real mode uses the official YouTube Analytics API v2 `reports.query` endpoint. It does not scrape YouTube Studio.

```bash
python -m raatverse_agent analytics fetch <upload_id>
python -m raatverse_agent analytics update-scores
python -m raatverse_agent strategy recommend
```

Required setup:

1. Enable YouTube Data API v3.
2. Enable YouTube Analytics API.
3. Add scopes in `.env`:

```env
YOUTUBE_SCOPES=https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/yt-analytics.readonly https://www.googleapis.com/auth/youtube.readonly
```

4. Re-run OAuth URL/code exchange after changing scopes.

If the token or env config is missing analytics scopes, the workflow saves a `snapshot_failed` record with a clear error.

## Metrics

Phase 6 stores:

- `views`
- `likes`
- `comments`
- `shares`
- `estimated_minutes_watched`
- `average_view_duration`
- `subscribers_gained`
- `subscribers_lost`
- derived `like_rate`, `comment_rate`, `subscriber_gain_rate`
- derived `retention_score`, `performance_score`, `confidence`

## Snapshot Windows

Supported windows are:

- `24h`
- `48h`
- `7d`
- `manual`

Due detection:

```bash
python -m raatverse_agent analytics due
```

This lists uploads that are old enough for a 24-hour, 48-hour, or 7-day snapshot and do not already have that window stored.

## Limitations

YouTube Analytics reports are date-based and may lag behind real-time YouTube Studio. Early snapshots should be treated as directional, not final. CTR and impressions are left for a later phase.

## References

- YouTube Analytics API `reports.query`: https://developers.google.com/youtube/analytics/reference/reports/query
- YouTube Analytics metrics: https://developers.google.com/youtube/analytics/metrics
