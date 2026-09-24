import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import Event, Task, User
from app.schemas import TaskCreate, TaskRead, TaskUpdate
from app.services.event_service import write_audit

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskRead])
def list_tasks(
    status: str | None = None,
    event_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Task]:
    query = db.query(Task)
    if status:
        query = query.filter(Task.status == status)
    if event_id:
        query = query.filter(Task.event_id == event_id)
    return query.order_by(Task.created_at.desc()).all()


@router.post("", response_model=TaskRead)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    if not db.get(Event, payload.event_id):
        raise HTTPException(status_code=404, detail="event not found")
    task = Task(**payload.model_dump(), id=str(uuid.uuid4()), status="pending")
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: str,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    before = {"status": task.status, "result": task.result}
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(task, field, value)
    if task.status == "completed":
        event = db.get(Event, task.event_id)
        if event and task.result in {"on_site_handled", "false_alarm", "no_action_needed"}:
            event.status = "closed"
    db.commit()
    db.refresh(task)
    write_audit(db, current_user.id, "update_task", "task", task.id, before, data)
    db.commit()
    return task


@router.post("/escalate-overdue", response_model=list[TaskRead])
def escalate_overdue(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Task]:
    now = datetime.utcnow()
    tasks = db.query(Task).filter(Task.status == "pending", Task.due_at < now).all()
    for task in tasks:
        task.status = "escalated"
        write_audit(db, current_user.id, "escalate_task", "task", task.id, {"status": "pending"}, {"status": "escalated"})
    db.commit()
    return tasks
