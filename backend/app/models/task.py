from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"))
    assignee_id: Mapped[str] = mapped_column(String(36))
    assignee_role: Mapped[str] = mapped_column(String(30), default="security")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    due_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    result: Mapped[str | None] = mapped_column(String(40), default=None)
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

