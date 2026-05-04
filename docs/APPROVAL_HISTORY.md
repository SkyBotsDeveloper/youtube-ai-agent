# Approval History

Phase 10 adds `approval_events` for lightweight review history.

Events are written when operators:

- approve or reject scripts,
- regenerate rejected scripts,
- prepare assets,
- create renders,
- prepare YouTube upload metadata,
- approve upload records.

Dashboard script detail pages show the script approval history. Recent approval history is also shown on `/dashboard`.

CLI examples:

```bash
python -m raatverse_agent script approve 1 --comment "Ready for dark cinematic render."
python -m raatverse_agent script reject 1 --reason "Weak twist" --comment "Needs a sharper final reveal."
python -m raatverse_agent youtube approve-upload 1 --comment "Metadata reviewed."
```

Important events are also mirrored to `audit_logs`.
