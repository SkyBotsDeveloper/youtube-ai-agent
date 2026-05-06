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

If captions appear slightly early in a real render, tune:

```env
SUBTITLE_GLOBAL_OFFSET_SECONDS=0.35
SUBTITLE_END_PADDING_SECONDS=0.15
```

The render timing alignment applies this offset after scaling subtitles to the actual TTS audio duration when available. The goal is for captions to appear with or just after speech, not before it.

## CTA and Audio-Based Timing

The render workflow now treats the generated audio duration as the timing source when available. Before rendering it:

- scales scene timings to the audio duration
- reserves the final CTA/outro segment first
- guarantees the CTA beat is at least `CTA_MIN_DURATION_SECONDS`
- adds end padding with `CTA_END_PADDING_SECONDS`
- keeps the final CTA subtitle visible long enough
- enforces `MIN_SCENE_BEAT_DURATION_SECONDS` and `MIN_SUBTITLE_DURATION_SECONDS`

Recommended timing settings:

```env
CTA_MIN_DURATION_SECONDS=7
CTA_END_PADDING_SECONDS=1.5
CTA_VISUAL_HOLD_SECONDS=2
MIN_SCENE_BEAT_DURATION_SECONDS=2.5
MIN_SUBTITLE_DURATION_SECONDS=1.2
SUBTITLE_GLOBAL_OFFSET_SECONDS=0.35
SUBTITLE_END_PADDING_SECONDS=0.15
```

The FFmpeg renderer creates a dedicated final outro screen with a dark cinematic background, RaatVerse text, the two-line subscribe CTA, and an optional generic red subscribe button. This is local FFmpeg composition only; it does not change YouTube upload behavior.

Outro button config:

```env
OUTRO_SUBSCRIBE_BUTTON_ENABLED=true
OUTRO_SUBSCRIBE_BUTTON_TEXT=Subscribe
OUTRO_SUBSCRIBE_BUTTON_STYLE=red
```

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
- CTA duration is below the configured minimum
- any scene beat or subtitle is too short
- audio duration would exceed final video duration
- too many beats have low visual relevance

Warnings do not block rendering by default. To block poor-quality plans:

```bash
python -m raatverse_agent render validate 1 --strict-quality
python -m raatverse_agent render create 1 --strict-quality
```

After `render create`, the CLI prints a timing report with audio duration, final video duration, CTA duration, shortest beat duration, subtitle count, subtitle offset, subtitle timing source, CTA TTS mode, outro screen/button flags, whether timing was scaled to audio, and warnings.

Use the asset quality report before rendering:

```bash
python -m raatverse_agent assets quality 1
```

For better real output, generate scripts with scene-specific `stock_search_query` values, prepare assets with downloads enabled, review repeated URLs, then render.
