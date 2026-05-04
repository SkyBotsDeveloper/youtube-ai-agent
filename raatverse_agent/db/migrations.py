from __future__ import annotations

from pathlib import Path
from typing import Any

from raatverse_agent.config import Settings


class MigrationError(RuntimeError):
    pass


def _alembic():
    try:
        from alembic import command
        from alembic.config import Config
    except ModuleNotFoundError as exc:
        raise MigrationError(
            "Alembic is not installed. Run `pip install -r requirements.txt` before using migration commands."
        ) from exc
    return command, Config


def _alembic_runtime():
    try:
        from alembic.migration import MigrationContext
        from alembic.script import ScriptDirectory
    except ModuleNotFoundError as exc:
        raise MigrationError(
            "Alembic is not installed. Run `pip install -r requirements.txt` before using migration commands."
        ) from exc
    return MigrationContext, ScriptDirectory


def alembic_config(settings: Settings):
    _, config_cls = _alembic()
    root = Path(__file__).resolve().parents[2]
    cfg = config_cls(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "raatverse_migrations"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def upgrade_database(settings: Settings, revision: str = "head") -> None:
    command, _ = _alembic()
    command.upgrade(alembic_config(settings), revision)


def current_revision(settings: Settings, verbose: bool = False) -> None:
    command, _ = _alembic()
    command.current(alembic_config(settings), verbose=verbose)


def migration_history(settings: Settings) -> None:
    command, _ = _alembic()
    command.history(alembic_config(settings), verbose=False)


def create_migration(settings: Settings, message: str = "schema update") -> None:
    command, _ = _alembic()
    command.revision(alembic_config(settings), message=message, autogenerate=True)


def migration_status(settings: Settings) -> dict[str, Any]:
    from raatverse_agent.db.session import get_engine

    migration_context_cls, script_directory_cls = _alembic_runtime()
    cfg = alembic_config(settings)
    script = script_directory_cls.from_config(cfg)
    heads = list(script.get_heads())
    head = heads[0] if heads else None
    try:
        with get_engine(settings.database_url).connect() as connection:
            context = migration_context_cls.configure(connection)
            current = context.get_current_revision()
    except Exception as exc:
        return {
            "current": None,
            "head": head,
            "is_current": False,
            "pending": heads,
            "error": str(exc),
        }

    pending = []
    if current != head and head:
        pending = [revision.revision for revision in script.walk_revisions(base=current, head=head)]
    return {
        "current": current,
        "head": head,
        "is_current": current == head,
        "pending": pending,
        "error": None,
    }


def check_migrations(settings: Settings) -> dict[str, Any]:
    status = migration_status(settings)
    status["message"] = (
        "Database schema is at the latest migration."
        if status.get("is_current")
        else "Database has pending migrations; run python -m raatverse_agent db safe-upgrade."
    )
    return status


def safe_upgrade_database(settings: Settings, revision: str = "head") -> dict[str, Any]:
    from raatverse_agent.db.persistence import PersistenceError, backup_database, database_status, sqlite_db_path

    before = migration_status(settings)
    backup_path: Path | None = None
    backup_error: str | None = None
    if settings.database_url.startswith("sqlite") and settings.db_backup_before_upgrade:
        try:
            db_path = sqlite_db_path(settings.database_url)
            if db_path.exists():
                backup_path = backup_database(settings)
            elif settings.release_backup_required:
                backup_error = f"No SQLite database file exists yet at {db_path}; backup skipped for first upgrade."
        except PersistenceError as exc:
            if settings.release_backup_required:
                raise MigrationError(str(exc)) from exc
            backup_error = str(exc)

    upgrade_database(settings, revision)
    after = migration_status(settings)
    health = database_status(settings)
    return {
        "backup_path": str(backup_path) if backup_path else None,
        "backup_error": backup_error,
        "before": before,
        "after": after,
        "db_status": health,
        "rollback_command": (
            f"python -m raatverse_agent db restore \"{backup_path}\" --confirm"
            if backup_path
            else "No rollback backup was created."
        ),
    }
