# Video Rendering

Phase 4 adds local video render records and render output files from approved `AssetPlan` records. It does not upload to YouTube.

## Mock Render Mode

Mock mode does not require FFmpeg. It creates a small placeholder `.mp4` file and stores a `video_renders` row.

```bash
python -m raatverse_agent db init
python -m raatverse_agent script generate --category horror --mock
python -m raatverse_agent script approve 1
python -m raatverse_agent assets prepare 1 --mock
python -m raatverse_agent render validate 1
python -m raatverse_agent render create 1 --mock
python -m raatverse_agent render list
python -m raatverse_agent render show 1
```

## FFmpeg Render Mode

Set:

```env
VIDEO_RENDERER=ffmpeg
FFMPEG_BINARY=ffmpeg
RENDER_OUTPUT_DIR=./outputs/renders
```

Run:

```bash
python -m raatverse_agent render create 1
```

The FFmpeg renderer:

- creates a vertical MP4 at `1080x1920`
- uses configured FPS, codecs, CRF, and preset
- uses asset plan scene timings
- uses local media files when available
- falls back to dark cinematic generated backgrounds when no local media is available
- uses real audio if the linked audio asset is not mock and the file exists
- falls back to silent audio for mock or missing audio
- burns `.ass` subtitles into the video
- adds a small text watermark when enabled

## Output

Default output directory:

```text
./outputs/renders
```

Files include:

- `render-<uid>.mp4`
- `subtitles/render-<uid>.ass`

## Subtitles

The renderer generates `.ass` subtitle files with:

- bold high-contrast captions
- white text
- black outline and shadow
- lower-middle safe area placement
- line wrapping for Shorts-style readability
- Unicode-safe UTF-8 output for Hindi/Hinglish text

## Watermark

Configuration:

```env
WATERMARK_ENABLED=true
WATERMARK_TEXT=RaatVerse
WATERMARK_POSITION=top-right
```

Supported positions:

- `top-right`
- `top-left`
- `bottom-right`
- `bottom-left`

## Statuses

- `render_pending`
- `render_running`
- `render_ready`
- `render_failed`

If FFmpeg is missing or a command fails, the render is saved as `render_failed` with a clear error message.

## Render Quality Preflight

Before rendering, the workflow now warns when:

- the same stock media URL appears in multiple scene beats
- less than 70% of beats have unique media
- narration audio duration is more than 15% longer than the estimated script duration

Warnings do not block rendering by default. To block poor-quality plans:

```bash
python -m raatverse_agent render validate 1 --strict-quality
python -m raatverse_agent render create 1 --strict-quality
```

Use the asset quality report before rendering:

```bash
python -m raatverse_agent assets quality 1
```

For better real output, generate scripts with scene-specific `stock_search_query` values, prepare assets with downloads enabled, review repeated URLs, then render.
