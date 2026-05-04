# Audit Export

Audit logs can be exported for release review or incident checks.

## CLI

```bash
python -m raatverse_agent audit export-json
python -m raatverse_agent audit export-csv
python -m raatverse_agent audit export-json --action script_approve
python -m raatverse_agent audit export-csv --entity-type youtube_upload
```

Filters:

- `--action`
- `--entity-type`
- `--since`
- `--until`
- `--limit`

Exports are written to:

```env
AUDIT_EXPORT_DIR=./outputs/audit_exports
```

## API

- `GET /audit/export.json`
- `GET /audit/export.csv`

The API supports the same filter query parameters.
