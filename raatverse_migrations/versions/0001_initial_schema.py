"""Initial RaatVerse schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-04
"""
from __future__ import annotations

from alembic import op

from raatverse_agent.db.models import Base


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(Base.metadata.sorted_tables):
        table.drop(bind=bind, checkfirst=True)
