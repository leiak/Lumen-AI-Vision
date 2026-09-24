from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import Event, Task, User

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


@router.get("/summary")
def summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    events = db.query(Event).all()
    tasks = db.query(Task).all()
    return {
        "event_total": len(events),
        "event_by_status": _count(events, lambda item: item.status),
        "event_by_risk": _count(events, lambda item: item.risk_level),
        "task_total": len(tasks),
        "task_by_status": _count(tasks, lambda item: item.status),
        "task_close_rate": round(sum(task.status == "completed" for task in tasks) / len(tasks), 4) if tasks else 0,
    }


def _count(items: list, key) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in items:
        value = key(item)
        result[value] = result.get(value, 0) + 1
    return result
