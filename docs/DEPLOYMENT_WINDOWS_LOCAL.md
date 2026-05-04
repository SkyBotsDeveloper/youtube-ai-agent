# Windows Local Production-Style Setup

This mode keeps everything local and free-first.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Install FFmpeg and ensure `ffmpeg.exe` is on PATH if using real rendering.

## Initialize

```powershell
python -m raatverse_agent db init
python -m raatverse_agent db safe-upgrade
python -m raatverse_agent ops doctor
python -m raatverse_agent ops e2e-check --mock
```

## Run FastAPI

```powershell
uvicorn raatverse_agent.api.main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/dashboard
```

## Backup

```powershell
python -m raatverse_agent db backup
python -m raatverse_agent db export-json
python -m raatverse_agent audit export-json
```

Keep `AUTO_UPLOAD=false`; use private upload and manual approval only.
