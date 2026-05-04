"""Add TTS quality metadata fields.

Revision ID: 0003_quality_patch_tts_media
Revises: 0002_approval_events
Create Date: 2026-05-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0003_quality_patch_tts_media"
down_revision = "0002_approval_events"
branch_labels = None
depends_on = None


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return
    existing = {item["name"] for item in inspector.get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def upgrade() -> None:
    _add_column_if_missing(
        "script_drafts",
        sa.Column("tts_narration_script", sa.Text(), nullable=True),
    )
    _add_column_if_missing("audio_assets", sa.Column("tts_text", sa.Text(), nullable=True))
    _add_column_if_missing("audio_assets", sa.Column("tts_chunks_json", sa.JSON(), nullable=True))
    _add_column_if_missing("audio_assets", sa.Column("tts_quality_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "audio_assets" in inspector.get_table_names():
        existing = {item["name"] for item in inspector.get_columns("audio_assets")}
        for name in ("tts_quality_json", "tts_chunks_json", "tts_text"):
            if name in existing:
                op.drop_column("audio_assets", name)
    if "script_drafts" in inspector.get_table_names():
        existing = {item["name"] for item in inspector.get_columns("script_drafts")}
        if "tts_narration_script" in existing:
            op.drop_column("script_drafts", "tts_narration_script")
