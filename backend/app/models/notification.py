from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"))
    task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tasks.id"), default=None)
    receiver_id: Mapped[str] = mapped_column(String(36))
    receiver_role: Mapped[str] = mapped_column(String(30), default="security")
    channel: Mapped[str] = mapped_column(String(30), default="in_app")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)