from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TrainingSample(Base):
    __tablename__ = "training_samples"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"))
    review_id: Mapped[str] = mapped_column(String(36), ForeignKey("reviews.id"))
    label: Mapped[str] = mapped_column(String(50))
    risk_level: Mapped[str] = mapped_column(String(20))
    reviewer_id: Mapped[str] = mapped_column(String(36))
    used_for_training: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
