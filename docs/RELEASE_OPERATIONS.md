# Release Operations

Phase 10 adds release-readiness helpers for local/VPS deployments.

## Commands

```bash
python -m raatverse_agent release status
python -m raatverse_agent release checklist
python -m raatverse_agent release prepare --version 0.1.0
python -m raatverse_agent release notes
```

`release prepare` checks the current version, creates a SQLite backup when required, reports migration status, prints safety warnings, and lists next deployment steps.

## Required Safety

Keep:

```env
AUTO_UPLOAD=false
AUTO_UPLOAD_MUST_BE_APPROVED=true
CONFIRM_ENABLE_AUTO_UPLOAD=false
```

Run `ops doctor` before restarting a production service.
