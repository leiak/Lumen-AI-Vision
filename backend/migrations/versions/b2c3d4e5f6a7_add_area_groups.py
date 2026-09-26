"""add area groups

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-25 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "area_groups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dedup_window_seconds", sa.Integer(), nullable=False, server_default="600"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "area_group_members",
        sa.Column("area_group_id", sa.String(length=36), nullable=False),
        sa.Column("area_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["area_group_id"], ["area_groups.id"]),
        sa.ForeignKeyConstraint(["area_id"], ["areas.id"]),
        sa.PrimaryKeyConstraint("area_group_id", "area_id"),
    )


def downgrade() -> None:
    op.drop_table("area_group_members")
    op.drop_table("area_groups")