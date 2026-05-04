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
