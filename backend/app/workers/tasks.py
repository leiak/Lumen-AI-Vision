import time
import uuid
from datetime import datetime

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import Area, Event, Keyframe, ModelResult, Task
from app.services.vl_service import explain_event
from app.workers.celery_app import celery_app


@celery_app.task(name="tasks.escalate_overdue")
def escalate_overdue() -> int:
    db = SessionLocal()
    try:
        tasks = db.query(Task).filter(Task.status == "pending", Task.due_at < datetime.utcnow()).all()
        for task in tasks:
            task.status = "escalated"
        db.commit()
        return len(tasks)
    finally:
        db.close()


@celery_app.task(name="tasks.explain_event")
def explain_event_task(event_id: str) -> dict:
    db = SessionLocal()
    try:
        event = db.get(Event, event_id)
        if not event:
            return {"event_id": event_id, "status": "missing"}
        started = time.perf_counter()
        keyframes = db.query(Keyframe).filter(Keyframe.event_id == event.id).all()
        summary, output, score = explain_event(event, keyframes)
        settings = get_settings()
        result = ModelResult(
            id=str(uuid.uuid4()),
            event_id=event.id,
            model_name=settings.vl_model_name,
            model_version=settings.vl_model_version,
            model_type="vl",
            label="event_explanation",
            score=score,
            output=output,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        event.summary = summary
        db.add(result)
        db.commit()
        return {"event_id": event.id, "status": "explained"}
    finally:
        db.close()
