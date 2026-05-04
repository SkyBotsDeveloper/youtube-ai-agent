# End-to-End Mock Dry Run

Phase 10 adds a single offline readiness check:

```bash
python -m raatverse_agent ops e2e-check --mock
```

It verifies:

- database status,
- SQLite backup availability,
- safe full mock workflow,
- mock asset/render/upload path,
- mock analytics,
- review queue,
- ops doctor warnings.

It does not call real LLM, TTS, media, YouTube, or analytics APIs.
