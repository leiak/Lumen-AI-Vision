from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"))
    reviewer_id: Mapped[str] = mapped_column(String(36))
    result: Mapped[str] = mapped_column(String(20))
    corrected_event_type: Mapped[str | None] = mapped_column(String(40), default=None)
    corrected_risk_level: Mapped[str | None] = mapped_column(String(20), default=None)
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    used_for_training: Mapped[bool] = mapped_column(Boolean, default=False)

