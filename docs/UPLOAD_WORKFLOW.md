# Upload Workflow

Phase 5 uses a strict approval flow.

## Required State

A video cannot upload unless:

- the render status is `render_ready`
- the render output file exists
- a YouTube upload record exists
- the upload record is explicitly `upload_approved`

Mock/dev mode can use `--approve-now`, but normal workflow should approve first.

## Commands

```bash
python -m raatverse_agent youtube metadata-preview 1
python -m raatverse_agent youtube prepare-upload 1
python -m raatverse_agent youtube approve-upload 1
python -m raatverse_agent youtube upload 1 --mock
python -m raatverse_agent youtube list
python -m raatverse_agent youtube show 1
```

## Statuses

- `upload_pending`
- `upload_approved`
- `upload_running`
- `upload_private`
- `upload_scheduled`
- `upload_failed`

## Metadata

Metadata is generated from the `ScriptDraft`, `AssetPlan`, and `VideoRender`:

- title under YouTube limits
- short description
- RaatVerse CTA
- safe hashtags
- stock media source notes when available
- tags for RaatVerse, Hindi horror/mystery/suspense, Shorts, category, and story type
- category ID `24` by default
- made for kids set to `false`
- contains synthetic media set from config
