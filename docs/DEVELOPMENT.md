# Development

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m raatverse_agent db init
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m raatverse_agent db init
```

## Run the Mock Pipeline

```bash
python -m raatverse_agent pipeline run --mock
```

## Generate Script Drafts

Mock mode:

```bash
python -m raatverse_agent script generate --category horror --mock
python -m raatverse_agent script list
python -m raatverse_agent script show 1
python -m raatverse_agent script approve 1
python -m raatverse_agent script reject 1 --reason "Needs a stronger twist."
python -m raatverse_agent script regenerate 1 --mock
python -m raatverse_agent tts generate 1 --mock
python -m raatverse_agent assets prepare 1 --mock
python -m raatverse_agent assets list
python -m raatverse_agent render validate 1
python -m raatverse_agent render create 1 --mock
python -m raatverse_agent render list
python -m raatverse_agent youtube metadata-preview 1
python -m raatverse_agent youtube prepare-upload 1
python -m raatverse_agent youtube approve-upload 1
python -m raatverse_agent youtube upload 1 --mock
python -m raatverse_agent youtube list
```

Real Gemini-compatible mode:

```bash
python -m raatverse_agent script generate --category horror
```

Real mode requires `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, and optionally `LLM_BASE_URL` in `.env`.

## Run the API

```bash
uvicorn raatverse_agent.api.main:app --reload
```

Open:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

## Run Tests

```bash
pytest
```

## Code Guidelines

- Keep credentials out of code and commits.
- Add real providers behind service interfaces.
- Keep upload behavior private or human-approved by default.
- Keep the daily cadence to one unique original Short unless explicitly changed by the operator.
