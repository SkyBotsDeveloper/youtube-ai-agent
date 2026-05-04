from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy import inspect, text
from sqlalchemy.exc import NoSuchModuleError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from raatverse_agent.config import get_settings
from raatverse_agent.db.models import Base

_engine_cache: dict[str, Engine] = {}
_session_factory_cache: dict[str, sessionmaker[Session]] = {}


def _ensure_sqlite_parent(database_url: str) -> None:
    if not database_url.startswith("sqlite:///") or database_url == "sqlite:///:memory:":
        return

    raw_path = database_url.replace("sqlite:///", "", 1)
    if raw_path.startswith(":memory:"):
        return

    Path(raw_path).expanduser().parent.mkdir(parents=True, exist_ok=True)


def create_db_engine(database_url: str) -> Engine:
    _ensure_sqlite_parent(database_url)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    kwargs = {"poolclass": StaticPool} if database_url == "sqlite:///:memory:" else {}
    try:
        return create_engine(database_url, future=True, connect_args=connect_args, **kwargs)
    except (ModuleNotFoundError, NoSuchModuleError) as exc:
        if database_url.startswith(("postgres://", "postgresql://")):
            raise RuntimeError(
                "Postgres DATABASE_URL was provided, but a Postgres SQLAlchemy driver is not installed. "
                "Install an optional driver such as psycopg/psycopg2, or use the default SQLite DATABASE_URL."
            ) from exc
        raise


def get_engine(database_url: str | None = None) -> Engine:
    resolved_url = database_url or get_settings().database_url
    if resolved_url not in _engine_cache:
        _engine_cache[resolved_url] = create_db_engine(resolved_url)
    return _engine_cache[resolved_url]


def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    resolved_url = database_url or get_settings().database_url
    if resolved_url not in _session_factory_cache:
        _session_factory_cache[resolved_url] = sessionmaker(
            bind=get_engine(resolved_url),
            autoflush=False,
            expire_on_commit=False,
        )
    return _session_factory_cache[resolved_url]


def dispose_engine(database_url: str | None = None) -> None:
    resolved_url = database_url or get_settings().database_url
    engine = _engine_cache.pop(resolved_url, None)
    _session_factory_cache.pop(resolved_url, None)
    if engine is not None:
        engine.dispose()


def initialize_database(database_url: str | None = None) -> Engine:
    engine = get_engine(database_url)
    Base.metadata.create_all(bind=engine)
    _run_sqlite_migrations(engine)
    return engine


def _run_sqlite_migrations(engine: Engine) -> None:
    """Small SQLite MVP migration layer for additive Phase table extensions."""

    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    migrations: dict[str, dict[str, str]] = {
        "script_drafts": {
            "tts_narration_script": "TEXT",
        },
        "audio_assets": {
            "tts_text": "TEXT",
            "tts_chunks_json": "JSON",
            "tts_quality_json": "JSON",
        },
        "analytics_snapshots": {
            "youtube_upload_id": "INTEGER",
            "youtube_video_id": "VARCHAR(128)",
            "script_draft_id": "INTEGER",
            "category": "VARCHAR(80)",
            "story_type": "VARCHAR(80)",
            "snapshot_window": "VARCHAR(20) DEFAULT 'manual'",
            "snapshot_date": "DATETIME",
            "days_since_upload": "FLOAT DEFAULT 0.0",
            "shares": "INTEGER DEFAULT 0",
            "estimated_minutes_watched": "FLOAT DEFAULT 0.0",
            "average_view_duration": "FLOAT DEFAULT 0.0",
            "subscribers_gained": "INTEGER DEFAULT 0",
            "subscribers_lost": "INTEGER DEFAULT 0",
            "like_rate": "FLOAT DEFAULT 0.0",
            "comment_rate": "FLOAT DEFAULT 0.0",
            "subscriber_gain_rate": "FLOAT DEFAULT 0.0",
            "retention_score": "FLOAT DEFAULT 0.0",
            "performance_score": "FLOAT DEFAULT 0.0",
            "confidence": "FLOAT DEFAULT 0.0",
            "raw_response_json": "JSON",
            "provider": "VARCHAR(80) DEFAULT 'mock'",
            "status": "VARCHAR(40) DEFAULT 'snapshot_ready'",
            "error_message": "TEXT",
            "created_at": "DATETIME",
            "updated_at": "DATETIME",
        },
        "category_scores": {
            "story_type": "VARCHAR(80)",
            "total_videos": "INTEGER DEFAULT 0",
            "avg_views": "FLOAT DEFAULT 0.0",
            "avg_likes": "FLOAT DEFAULT 0.0",
            "avg_comments": "FLOAT DEFAULT 0.0",
            "avg_like_rate": "FLOAT DEFAULT 0.0",
            "avg_comment_rate": "FLOAT DEFAULT 0.0",
            "avg_average_view_duration": "FLOAT DEFAULT 0.0",
            "avg_subscribers_gained": "FLOAT DEFAULT 0.0",
            "avg_performance_score": "FLOAT DEFAULT 0.0",
            "trend_score": "FLOAT DEFAULT 0.0",
            "confidence": "FLOAT DEFAULT 0.0",
            "last_updated": "DATETIME",
        },
    }

    with engine.begin() as connection:
        for table, columns in migrations.items():
            if table not in table_names:
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


@contextmanager
def session_scope(database_url: str | None = None) -> Iterator[Session]:
    session = get_session_factory(database_url)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
