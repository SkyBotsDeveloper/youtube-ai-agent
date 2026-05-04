# Audit Logs

Phase 9 adds an `audit_logs` table for important human and operational actions.

## Logged Actions

- script approval,
- script rejection,
- rejected script regeneration,
- asset preparation,
- render creation,
- YouTube upload metadata preparation,
- YouTube upload approval,
- YouTube upload attempts,
- workflow runs triggered from CLI or dashboard,
- database JSON import,
- database restore,
- blocked dashboard auth attempts when token protection is enabled.

## CLI

```bash
python -m raatverse_agent audit list
python -m raatverse_agent audit list --action script_approve
python -m raatverse_agent audit show <id>
python -m raatverse_agent audit export-json
python -m raatverse_agent audit export-csv
```

## API

- `GET /audit/logs`
- `GET /audit/logs/{id}`

Filters:

```text
/audit/logs?action=script_approve
/audit/logs?entity_type=youtube_upload
```

Audit logs are operational records, not a replacement for full user accounts or role-based authorization.
