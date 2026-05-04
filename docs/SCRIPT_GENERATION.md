# Script Generation

Phase 2 adds human-review script drafts for RaatVerse Shorts. Real generation is limited to script text only; TTS, rendering, thumbnails, uploads, and analytics remain future phases.

## Supported Categories

- `horror`
- `mystery`
- `suspense`
- `emotional_twist`
- `thriller`
- `urban_legend`
- `psychological`

Each category has a structured prompt template with tone, premise direction, safety boundaries, timing structure, and a required JSON output schema.

## Mock Generation

```bash
python -m raatverse_agent db init
python -m raatverse_agent script generate --category horror --mock
python -m raatverse_agent script list
python -m raatverse_agent script show 1
python -m raatverse_agent script approve 1
python -m raatverse_agent script reject 1 --reason "Needs a stronger twist."
```

## Gemini-Compatible Generation

Configure `.env`:

```env
LLM_PROVIDER=gemini
LLM_API_KEY=replace-with-your-key
LLM_MODEL=replace-with-gemini-compatible-model
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta
LLM_TIMEOUT_SECONDS=30
LLM_TEMPERATURE=0.85
```

Run:

```bash
python -m raatverse_agent script generate --category horror
```

If `LLM_API_KEY` is missing, mock mode still works and real generation returns a clear configuration error.

## Draft Output

Each script draft stores:

- title
- category
- story type
- hook
- full narration script
- scene beats and visual suggestions
- subtitle-friendly lines
- CTA line
- estimated duration
- language style
- safety notes
- originality notes
- validation results

## Safety Rules

Generated stories must avoid:

- gore-heavy content
- explicit sexual content
- hate or slurs
- real-person fake allegations
- copied movie, anime, game, or celebrity characters
- misleading true-story claims
- graphic harm involving children
- repetitive templates and overused endings

The desired tone is suspenseful, atmospheric, cinematic, and safe for general teen/adult audiences.

## Validation and Originality

The validator checks:

- duration bounds
- CTA presence
- script length
- hook strength
- configured category
- Hindi/Hinglish language style
- blocked safety phrases
- scene beat presence
- similarity against prior draft titles, hooks, scripts, videos, and story ideas
- repeated category/story-type usage in recent drafts

Similarity checks are intentionally lightweight in Phase 2: normalized text, `difflib` similarity, and n-gram overlap. No external vector database is used.

## API Endpoints

- `POST /scripts/generate`
- `GET /scripts`
- `GET /scripts/{id}`
- `POST /scripts/{id}/approve`
- `POST /scripts/{id}/reject`
- `POST /scripts/{id}/revise`

The revise endpoint marks an existing draft as `needs_revision`; full automated revision is planned for a later phase.
