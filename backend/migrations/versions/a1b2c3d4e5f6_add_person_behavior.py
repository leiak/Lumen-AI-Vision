"""add person behavior

Revision ID: a1b2c3d4e5f6
Revises: edbbe804071c
Create Date: 2026-09-24 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "edbbe804071c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "person_tracks",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("vehicle_track_id", sa.String(length=64), nullable=False),
        sa.Column("camera_id", sa.String(length=36), nullable=False),
        sa.Column("area_id", sa.String(length=36), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["area_id"], ["areas.id"]),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"]),
        sa.ForeignKeyConstraint(["vehicle_track_id"], ["vehicle_tracks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_person_tracks_vehicle_track_id", "person_tracks", ["vehicle_track_id"])
    op.create_table(
        "person_behavior_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("person_track_id", sa.String(length=64), nullable=False),
        sa.Column("vehicle_track_id", sa.String(length=64), nullable=False),
        sa.Column("behavior_label", sa.String(length=50), nullable=False),
        sa.Column("behavior_confidence", sa.Float(), nullable=False),
        sa.Column("near_vehicle_seconds", sa.Float(), nullable=False),
        sa.Column("sequence_frame_count", sa.Integer(), nullable=False),
        sa.Column("sequence_start_time", sa.DateTime(), nullable=False),
        sa.Column("sequence_end_time", sa.DateTime(), nullable=False),
        sa.Column("model_type", sa.String(length=20), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["person_track_id"], ["person_tracks.id"]),
        sa.ForeignKeyConstraint(["vehicle_track_id"], ["vehicle_tracks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_person_behavior_results_event_id", "person_behavior_results", ["event_id"])
    op.create_index("ix_person_behavior_results_person_track_id", "person_behavior_results", ["person_track_id"])


def downgrade() -> None:
    op.drop_index("ix_person_behavior_results_person_track_id", table_name="person_behavior_results")
    op.drop_index("ix_person_behavior_results_event_id", table_name="person_behavior_results")
    op.drop_table("person_behavior_results")
    op.drop_index("ix_person_tracks_vehicle_track_id", table_name="person_tracks")
    op.drop_table("person_tracks")
