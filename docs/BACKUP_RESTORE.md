# Backup and Restore

Phase 8 adds SQLite backup, restore, and JSON export/import commands.

## Backup

```bash
python -m raatverse_agent db backup
python -m raatverse_agent db backups
```

Config:

```env
DB_BACKUP_DIR=./outputs/backups
DB_BACKUP_RETENTION=20
```

## JSON Export

```bash
python -m raatverse_agent db export-json
```

Config:

```env
DB_EXPORT_DIR=./outputs/exports
```

## JSON Import

Import only into an empty database:

```bash
python -m raatverse_agent db import-json ./outputs/exports/raatverse-export-example.json --confirm
```

The command refuses to import into non-empty tables.

## Restore SQLite Backup

```bash
python -m raatverse_agent db restore ./outputs/backups/raatverse_agent-example.sqlite3 --confirm
```

Restore overwrites the current SQLite database file, so `--confirm` is required.

## Status

```bash
python -m raatverse_agent db status
```

This prints engine, path, size, and table names.
