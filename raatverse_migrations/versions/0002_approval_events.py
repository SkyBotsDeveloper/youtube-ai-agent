"""Add approval event history.

Revision ID: 0002_approval_events
Revises: 0001_initial_schema
Create Date: 2026-05-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0002_approval_events"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "approval_events" not in inspector.get_table_names():
        op.create_table(
            "approval_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("entity_type", sa.String(length=80), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(length=120), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("actor", sa.String(length=120), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    for name, columns in {
        "ix_approval_events_entity_type": ["entity_type"],
        "ix_approval_events_entity_id": ["entity_id"],
        "ix_approval_events_action": ["action"],
        "ix_approval_events_actor": ["actor"],
        "ix_approval_events_created_at": ["created_at"],
    }.items():
        if name not in {index["name"] for index in inspector.get_indexes("approval_events")}:
            op.create_index(name, "approval_events", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "approval_events" in inspector.get_table_names():
        op.drop_table("approval_events")
