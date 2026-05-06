"""Add render timing report metadata.

Revision ID: 0004_render_timing_report
Revises: 0003_quality_patch_tts_media
Create Date: 2026-05-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0004_render_timing_report"
down_revision = "0003_quality_patch_tts_media"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "video_renders" not in inspector.get_table_names():
        return
    existing = {item["name"] for item in inspector.get_columns("video_renders")}
    if "timing_report_json" not in existing:
        op.add_column("video_renders", sa.Column("timing_report_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "video_renders" not in inspector.get_table_names():
        return
    existing = {item["name"] for item in inspector.get_columns("video_renders")}
    if "timing_report_json" in existing:
        op.drop_column("video_renders", "timing_report_json")
