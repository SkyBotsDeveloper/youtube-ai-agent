from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, Integer, inspect, select

from raatverse_agent.config import Settings
from raatverse_agent.db.models import Base
from raatverse_agent.db.session import dispose_engine, get_engine, initialize_database


class PersistenceError(RuntimeError):
    pass


def sqlite_db_path(database_url: str) -> Path:
    if database_url == "sqlite:///:memory:":
        raise PersistenceError("In-memory SQLite databases cannot be backed up or restored as files.")
    if not database_url.startswith("sqlite:///"):
        raise PersistenceError("File backup/restore is only supported for SQLite DATABASE_URL values.")
    raw = database_url.replace("sqlite:///", "", 1)
    return Path(raw).expanduser().resolve()


def backup_database(settings: Settings) -> Path:
    source = sqlite_db_path(settings.database_url)
    if not source.exists():
        raise PersistenceError(f"SQLite database file does not exist: {source}")
    backup_dir = Path(settings.db_backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"{source.stem}-{timestamp}.sqlite3"
    shutil.copy2(source, target)
    _apply_retention(backup_dir, settings.db_backup_retention)
    return target


def list_backups(settings: Settings) -> list[Path]:
    backup_dir = Path(settings.db_backup_dir)
    if not backup_dir.exists():
        return []
    return sorted(
        [path for path in backup_dir.iterdir() if path.is_file() and path.suffix in {".db", ".sqlite", ".sqlite3"}],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def restore_database(settings: Settings, backup_path: str) -> Path:
    source = Path(backup_path).expanduser().resolve()
    if not source.exists():
        raise PersistenceError(f"Backup file does not exist: {source}")
    target = sqlite_db_path(settings.database_url)
    target.parent.mkdir(parents=True, exist_ok=True)
    dispose_engine(settings.database_url)
    shutil.copy2(source, target)
    initialize_database(settings.database_url)
    return target


def database_status(settings: Settings) -> dict[str, Any]:
    status = {
        "db_engine": settings.db_engine,
        "database_url": settings.database_url,
        "is_sqlite": settings.database_url.startswith("sqlite"),
        "path": None,
        "exists": None,
        "size_bytes": None,
        "tables": [],
    }
    if settings.database_url.startswith("sqlite:///") and settings.database_url != "sqlite:///:memory:":
        path = sqlite_db_path(settings.database_url)
        status.update(
            {
                "path": str(path),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else 0,
            }
        )
    try:
        engine = initialize_database(settings.database_url)
        status["tables"] = inspect(engine).get_table_names()
    except Exception as exc:
        status["error"] = str(exc)
    return status


def export_database_json(settings: Settings) -> Path:
    initialize_database(settings.database_url)
    engine = get_engine(settings.database_url)
    export_dir = Path(settings.db_export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = export_dir / f"raatverse-export-{timestamp}.json"
    data: dict[str, Any] = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "schema": "raatverse-json-export-v1",
        "tables": {},
    }
    with engine.connect() as connection:
        for table in Base.metadata.sorted_tables:
            rows = connection.execute(select(table)).mappings().all()
            data["tables"][table.name] = [
                {key: _serialize_value(value) for key, value in dict(row).items()}
                for row in rows
            ]
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def import_database_json(settings: Settings, path: str) -> dict[str, int]:
    source = Path(path).expanduser().resolve()
    if not source.exists():
        raise PersistenceError(f"JSON export does not exist: {source}")
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema") != "raatverse-json-export-v1":
        raise PersistenceError("Unsupported JSON export schema.")

    initialize_database(settings.database_url)
    engine = get_engine(settings.database_url)
    imported: dict[str, int] = {}
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            rows = payload.get("tables", {}).get(table.name, [])
            existing_count = connection.execute(select(table.c.id).limit(1)).first()
            if existing_count is not None and rows:
                raise PersistenceError(
                    f"Table '{table.name}' is not empty. Import JSON into an empty database."
                )
            if not rows:
                imported[table.name] = 0
                continue
            converted = [_convert_row(table, row) for row in rows]
            connection.execute(table.insert(), converted)
            imported[table.name] = len(converted)
    return imported


def _apply_retention(backup_dir: Path, retention: int) -> None:
    backups = sorted(
        [path for path in backup_dir.iterdir() if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old in backups[retention:]:
        old.unlink()


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _convert_row(table, row: dict[str, Any]) -> dict[str, Any]:
    converted: dict[str, Any] = {}
    for column in table.columns:
        if column.name not in row:
            continue
        value = row[column.name]
        if value is None:
            converted[column.name] = None
        elif isinstance(column.type, DateTime):
            parsed = datetime.fromisoformat(str(value))
            converted[column.name] = parsed
        elif isinstance(column.type, Integer):
            converted[column.name] = int(value)
        else:
            converted[column.name] = value
    return converted
