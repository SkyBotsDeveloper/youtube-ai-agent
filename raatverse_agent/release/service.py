from __future__ import annotations

from pathlib import Path
from typing import Any

from raatverse_agent.config import Settings
from raatverse_agent.db.migrations import check_migrations, migration_status
from raatverse_agent.db.persistence import PersistenceError, backup_database, database_status, list_backups
from raatverse_agent.ops.health import doctor_warnings


CHECKLIST = [
    "Install dependencies with pip install -r requirements.txt.",
    "Review .env and keep AUTO_UPLOAD=false.",
    "Run python -m raatverse_agent db safe-upgrade.",
    "Run python -m raatverse_agent ops doctor.",
    "Run python -m raatverse_agent ops e2e-check --mock.",
    "Open /dashboard and verify pending review items.",
    "Confirm backup cron is configured for SQLite deployments.",
]


def release_status(settings: Settings) -> dict[str, Any]:
    backups = list_backups(settings)
    return {
        "app_version": settings.app_version,
        "app_env": settings.app_env,
        "database": database_status(settings),
        "migration": migration_status(settings),
        "latest_backup": str(backups[0]) if backups else None,
        "safety_warnings": list(settings.safety_warnings),
        "doctor_warnings": doctor_warnings(settings),
    }


def release_checklist() -> list[str]:
    return list(CHECKLIST)


def release_notes() -> str:
    path = Path("CHANGELOG.md")
    if not path.exists():
        return "No CHANGELOG.md file found."
    return path.read_text(encoding="utf-8")


def prepare_release(settings: Settings, version: str) -> dict[str, Any]:
    backup_path = None
    backup_error = None
    if settings.database_url.startswith("sqlite") and settings.release_backup_required:
        try:
            backup_path = backup_database(settings)
        except PersistenceError as exc:
            backup_error = str(exc)

    migration = check_migrations(settings)
    warnings = list(settings.safety_warnings)
    warnings.extend(doctor_warnings(settings))
    return {
        "target_version": version,
        "current_version": settings.app_version,
        "backup_path": str(backup_path) if backup_path else None,
        "backup_error": backup_error,
        "migration": migration,
        "warnings": _dedupe(warnings),
        "next_steps": [
            "Review backup path and migration status.",
            "Run python -m raatverse_agent db safe-upgrade.",
            "Run python -m raatverse_agent ops doctor.",
            "Restart the FastAPI service or Docker container.",
            "Open /dashboard and verify review queue.",
        ],
    }


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
