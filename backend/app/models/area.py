from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Area(Base):
    __tablename__ = "areas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    camera_id: Mapped[str] = mapped_column(String(36), ForeignKey("cameras.id"))
    name: Mapped[str] = mapped_column(String(100))
    area_type: Mapped[str] = mapped_column(String(30), default="gate")
    polygon: Mapped[list | None] = mapped_column(JSON, default=list)
    stay_threshold_seconds: Mapped[int] = mapped_column(Integer, default=300)
    high_risk_seconds: Mapped[int] = mapped_column(Integer, default=600)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

