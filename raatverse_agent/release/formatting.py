from __future__ import annotations


def format_release_status(status: dict) -> str:
    warnings = status.get("safety_warnings") or []
    doctor = status.get("doctor_warnings") or []
    warning_lines = "\n".join(f"  - {warning}" for warning in [*warnings, *doctor]) or "  none"
    migration = status.get("migration", {})
    return (
        "RaatVerse release status\n"
        f"Version: {status.get('app_version')}\n"
        f"Environment: {status.get('app_env')}\n"
        f"Database engine: {status.get('database', {}).get('db_engine')}\n"
        f"Migration: {migration.get('current')} -> head {migration.get('head')}\n"
        f"Migration current: {migration.get('is_current')}\n"
        f"Latest backup: {status.get('latest_backup') or 'None'}\n"
        "Warnings:\n"
        f"{warning_lines}"
    )


def format_release_checklist(items: list[str]) -> str:
    return "RaatVerse release checklist\n" + "\n".join(f"{index}. {item}" for index, item in enumerate(items, 1))


def format_release_prepare(result: dict) -> str:
    warnings = result.get("warnings") or []
    warning_lines = "\n".join(f"  - {warning}" for warning in warnings) or "  none"
    steps = "\n".join(f"  - {step}" for step in result.get("next_steps", []))
    migration = result.get("migration", {})
    return (
        "RaatVerse release prepare\n"
        f"Current version: {result.get('current_version')}\n"
        f"Target version: {result.get('target_version')}\n"
        f"Backup: {result.get('backup_path') or result.get('backup_error') or 'None'}\n"
        f"Migration current: {migration.get('is_current')}\n"
        f"Migration message: {migration.get('message')}\n"
        "Warnings:\n"
        f"{warning_lines}\n"
        "Next steps:\n"
        f"{steps}"
    )
