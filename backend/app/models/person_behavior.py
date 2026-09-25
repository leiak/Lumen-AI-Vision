from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PersonTrack(Base):
    __tablename__ = "person_tracks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    vehicle_track_id: Mapped[str] = mapped_column(String(64), ForeignKey("vehicle_tracks.id"))
    camera_id: Mapped[str] = mapped_column(String(36), ForeignKey("cameras.id"))
    area_id: Mapped[str] = mapped_column(String(36), ForeignKey("areas.id"))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PersonBehaviorResult(Base):
    __tablename__ = "person_behavior_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"))
    person_track_id: Mapped[str] = mapped_column(String(64), ForeignKey("person_tracks.id"))
    vehicle_track_id: Mapped[str] = mapped_column(String(64), ForeignKey("vehicle_tracks.id"))
    behavior_label: Mapped[str] = mapped_column(String(50))
    behavior_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    near_vehicle_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    sequence_frame_count: Mapped[int] = mapped_column(Integer, default=0)
    sequence_start_time: Mapped[datetime] = mapped_column(DateTime)
    sequence_end_time: Mapped[datetime] = mapped_column(DateTime)
    model_type: Mapped[str] = mapped_column(String(20), default="rule")
    model_version: Mapped[str] = mapped_column(String(50), default="person-behavior-rule-v1")
    output: Mapped[dict | list | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    event = relationship("Event", back_populates="behavior_results")
