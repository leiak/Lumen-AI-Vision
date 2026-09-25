from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    camera_id: Mapped[str] = mapped_column(String(36), ForeignKey("cameras.id"))
    area_id: Mapped[str] = mapped_column(String(36), ForeignKey("areas.id"))
    track_id: Mapped[str] = mapped_column(String(64), ForeignKey("vehicle_tracks.id"))
    event_type: Mapped[str] = mapped_column(String(40))
    risk_level: Mapped[str] = mapped_column(String(20), default="medium")
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="candidate")
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    vehicle_plate_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    dedup_key: Mapped[str | None] = mapped_column(String(200), default=None, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    behavior_results: Mapped[list["PersonBehaviorResult"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
    )
