from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from fastapi.encoders import jsonable_encoder

from app.models import Event, Notification, Task, User
from app.services.notification_service import dispatch_notification


def write_audit(
    db: Session,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    before_value=None,
    after_value=None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    from app.models import AuditLog
    import uuid
    db.add(
        AuditLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
    before_value=jsonable_encoder(before_value) if before_value is not None else None,
    after_value=jsonable_encoder(after_value) if after_value is not None else None,
            ip=ip,
            user_agent=user_agent,
        )
    )


RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
BEHAVIOR_RISK_FLOOR = {
    "fall_down": "critical",
    "person_entering_vehicle": "high",
    "long_time_loitering": "high",
    "multiple_persons": "high",
    "loading_unloading": "low",
    "person_present": "low",
    "person_static": "low",
    "person_moving": "low",
    "unknown_behavior": "low",
}


def event_risk_level(area, duration_seconds: int, behaviors: list | None = None) -> str:
    base = "low"
    if duration_seconds >= area.high_risk_seconds:
        base = "high"
    elif duration_seconds >= area.stay_threshold_seconds:
        base = "medium"

    floor = "low"
    for behavior in behaviors or []:
        if float(behavior.behavior_confidence) < 0.5:
            continue
        candidate = BEHAVIOR_RISK_FLOOR.get(behavior.behavior_label, "low")
        if RISK_ORDER[candidate] > RISK_ORDER[floor]:
            floor = candidate

    return floor if RISK_ORDER[floor] > RISK_ORDER[base] else base


def create_task_for_event(db: Session, event: Event) -> Task:
    due_minutes = 2 if event.risk_level == "critical" else 5 if event.risk_level == "high" else 30
    assignee = (
        db.query(User)
        .filter(User.is_active.is_(True), User.role == "security")
        .order_by(User.created_at)
        .first()
        or db.query(User)
        .filter(User.is_active.is_(True), User.role == "admin")
        .order_by(User.created_at)
        .first()
    )
    assignee_id = assignee.id if assignee else "security-duty"
    assignee_role = assignee.role if assignee else "security"
    task = Task(
        id=f"task-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
        event_id=event.id,
        assignee_id=assignee_id,
        assignee_role=assignee_role,
        status="pending",
        due_at=datetime.utcnow() + timedelta(minutes=due_minutes),
    )
    db.add(task)
    db.flush()
    notification = Notification(
        id=f"ntf-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
        event_id=event.id,
        task_id=task.id,
        receiver_id=task.assignee_id,
        receiver_role=task.assignee_role,
        channel="in_app",
        status="pending",
    )
    db.add(notification)
    db.commit()
    dispatch_notification(db, notification, f"事件 {event.id} 风险等级为 {event.risk_level}，请及时处理。")
    return task
