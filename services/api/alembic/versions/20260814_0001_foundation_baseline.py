"""Milestone 2 foundation baseline (no domain schema)

Revision ID: 0001_foundation_baseline
Revises:
Create Date: 2026-08-14
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0001_foundation_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Establish Alembic version tracking. Domain schema starts in Milestone 4."""
    pass


def downgrade() -> None:
    pass
