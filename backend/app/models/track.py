from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VehicleTrack(Base):
    __tablename__ = "vehicle_tracks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    camera_id: Mapped[str] = mapped_column(String(36), ForeignKey("cameras.id"))
    area_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("areas.id"), default=None)
    vehicle_type: Mapped[str] = mapped_column(String(30), default="unknown")
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    enter_area_time: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    leave_area_time: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    static_seconds: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="moving")

