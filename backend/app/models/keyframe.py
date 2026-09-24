from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Keyframe(Base):
    __tablename__ = "keyframes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    track_id: Mapped[str] = mapped_column(String(64), ForeignKey("vehicle_tracks.id"))
    event_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("events.id"), default=None)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    storage_url: Mapped[str] = mapped_column(String(500))
    width: Mapped[int | None] = mapped_column(Integer, default=None)
    height: Mapped[int | None] = mapped_column(Integer, default=None)
    frame_role: Mapped[str] = mapped_column(String(30), default="state_change")
    quality_score: Mapped[float | None] = mapped_column(Float, default=None)
    detected_objects: Mapped[list | None] = mapped_column(JSON, default=list)
    privacy_processed: Mapped[bool] = mapped_column(Boolean, default=True)

