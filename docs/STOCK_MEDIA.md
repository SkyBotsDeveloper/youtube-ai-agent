# Stock Media

Phase 3 adds stock media search and source metadata for approved script drafts. It does not render videos.

## Providers

- `mock`: always works without external services.
- `pexels`: uses the Pexels API with a free API key.
- `pixabay`: uses the Pixabay API with a free API key.
- `both`: searches Pexels and Pixabay.

## Configuration

```env
STOCK_MEDIA_PROVIDER=mock
PEXELS_API_KEY=replace-with-free-pexels-key
PIXABAY_API_KEY=replace-with-free-pixabay-key
STOCK_MEDIA_RESULTS_PER_BEAT=3
STOCK_MEDIA_CACHE_DIR=./outputs/assets/media
STOCK_MEDIA_DOWNLOAD_ENABLED=false
STOCK_MEDIA_TIMEOUT_SECONDS=20
STOCK_MEDIA_AVOID_DUPLICATES=true
STOCK_MEDIA_MIN_UNIQUE_PER_PLAN=6
STOCK_MEDIA_PREFER_VERTICAL=true
STOCK_MEDIA_MAX_REUSE_PER_URL=1
VISUAL_RELEVANCE_MIN_SCORE=0.55
VISUAL_RELEVANCE_PREFER_LOCATION=true
VISUAL_RELEVANCE_PREFER_ACTION=true
VISUAL_RELEVANCE_PREFER_MOOD=true
```

Use mock mode:

```bash
python -m raatverse_agent assets prepare 1 --mock
```

Use Pexels:

```env
STOCK_MEDIA_PROVIDER=pexels
PEXELS_API_KEY=replace-with-free-pexels-key
```

Use Pixabay:

```env
STOCK_MEDIA_PROVIDER=pixabay
PIXABAY_API_KEY=replace-with-free-pixabay-key
```

If a required key is missing, the workflow saves an `asset_failed` plan with a clear error message. Mock mode remains available.

## Scene-Specific Queries

Script prompts now request scene-level visual metadata:

- `stock_search_query`
- `negative_keywords`
- `mood`
- `location`
- `camera_motion`

The media providers use these fields before falling back to generic category terms. Good queries should describe the visible scene, not just the genre:

```text
dark abandoned house interior night vertical
old wall texture dark room horror
scary hallway shadows night vertical
lonely man dark corridor suspense
dark cinematic room heartbeat horror
```

Pexels and Pixabay searches try alternate beat-specific queries when the first query is weak.

The query builder also uses the beat narration segment so visuals align with the audio scene more reliably. For example, narration about wall heartbeat sounds can produce:

```text
old wall texture dark room horror vertical
abandoned house wall close up dark
creepy interior wall shadows night vertical
```

## Diversity Filtering

Asset preparation now selects a diverse candidate per scene beat:

- avoids reusing the same source URL across beats when alternatives exist
- prefers unique videos per beat
- prefers vertical assets when configured
- penalizes repeated clips
- falls back to a local dark cinematic placeholder for weak beats

Run a quality report after preparing assets:

```bash
python -m raatverse_agent assets quality <asset_plan_id>
```

The report shows total beats, unique URLs, repeated URLs, vertical media count, missing local files, provider distribution, weak beats, and recommendations. `assets prepare` prints this report automatically.

Each beat now includes alignment details:

- narration excerpt
- selected media URL
- query used
- visual relevance score
- duration allocated
- CTA/outro flag
- warnings for weak alignment or short CTA timing

Visual relevance considers vertical fit, query match, uniqueness, provider availability, resolution, and optional location/action/mood matches.

## Attribution Metadata

Each media candidate stores:

- provider
- query used
- source URL
- creator name, when returned by the provider
- license or attribution note
- local file path, if downloaded
- media type
- width and height
- duration, for videos when returned
- scene beat index

Before publishing, verify the current provider license and attribution requirements.
