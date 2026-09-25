from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import Event, Notification, PersonBehaviorResult, Review, Task, User

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


@router.get("/operations")
def operations(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    now = datetime.utcnow()
    started_at = now - timedelta(days=days)
    events = db.query(Event).filter(Event.start_time >= started_at).all()
    tasks = db.query(Task).filter(Task.created_at >= started_at).all()
    notifications = (
        db.query(Notification)
        .join(Task, Notification.task_id == Task.id)
        .filter(Task.created_at >= started_at)
        .all()
    )
    reviews = db.query(Review).filter(Review.reviewed_at >= started_at).all()
    behaviors = (
        db.query(PersonBehaviorResult)
        .filter(PersonBehaviorResult.sequence_start_time >= started_at)
        .all()
    )

    completed_tasks = [task for task in tasks if task.status == "completed"]
    overdue_tasks = [
        task for task in tasks if task.status == "pending" and task.due_at and task.due_at < now
    ]
    task_on_time = [
        task for task in completed_tasks if task.due_at and task.updated_at <= task.due_at
    ]
    completion_minutes = [
        max(0.0, (task.updated_at - task.created_at).total_seconds() / 60)
        for task in completed_tasks
    ]
    notification_read = [item for item in notifications if item.status == "read"]
    notification_response_minutes = [
        max(0.0, (item.read_at - task.created_at).total_seconds() / 60)
        for item, task in (
            (notification, next((task for task in tasks if task.id == notification.task_id), None))
            for notification in notification_read
        )
        if task
    ]

    camera_groups: dict[str, list[Event]] = defaultdict(list)
    area_groups: dict[str, list[Event]] = defaultdict(list)
    daily_groups: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        camera_groups[event.camera_id].append(event)
        area_groups[event.area_id].append(event)
        daily_groups[event.start_time.date().isoformat()].append(event)

    task_groups: dict[str, list[Task]] = defaultdict(list)
    for task in tasks:
        task_groups[task.assignee_id].append(task)

    return {
        "window": {
            "days": days,
            "started_at": started_at.isoformat(),
            "ended_at": now.isoformat(),
            "last_event_at": max((event.start_time for event in events), default=None),
        },
        "events": {
            "total": len(events),
            "by_status": _count(events, lambda item: item.status),
            "by_risk": _count(events, lambda item: item.risk_level),
            "high_risk_total": sum(event.risk_level in {"high", "critical"} for event in events),
            "closed_rate": _rate(sum(event.status == "closed" for event in events), len(events)),
            "avg_duration_minutes": _average(
                [event.duration_seconds / 60 for event in events]
            ),
        },
        "tasks": {
            "total": len(tasks),
            "by_status": _count(tasks, lambda item: item.status),
            "close_rate": _rate(len(completed_tasks), len(tasks)),
            "overdue_total": len(overdue_tasks),
            "on_time_rate": _rate(len(task_on_time), len(completed_tasks)),
            "avg_completion_minutes": _average(completion_minutes),
            "by_assignee": {
                assignee_id: {
                    "total": len(items),
                    "completed": sum(item.status == "completed" for item in items),
                    "pending": sum(item.status == "pending" for item in items),
                    "escalated": sum(item.status == "escalated" for item in items),
                }
                for assignee_id, items in task_groups.items()
            },
        },
        "notifications": {
            "total": len(notifications),
            "by_status": _count(notifications, lambda item: item.status),
            "read_rate": _rate(len(notification_read), len(notifications)),
            "avg_response_minutes": _average(notification_response_minutes),
        },
        "reviews": {
            "total": len(reviews),
            "by_result": _count(reviews, lambda item: item.result),
            "normal_rate": _rate(sum(item.result == "normal" for item in reviews), len(reviews)),
            "abnormal_rate": _rate(sum(item.result == "abnormal" for item in reviews), len(reviews)),
            "uncertain_rate": _rate(sum(item.result == "uncertain" for item in reviews), len(reviews)),
        },
        "behaviors": {
            "total": len(behaviors),
            "by_label": _count(behaviors, lambda item: item.behavior_label),
            "by_model_type": _count(behaviors, lambda item: item.model_type),
            "high_confidence_total": sum(item.behavior_confidence >= 0.7 for item in behaviors),
            "avg_confidence": _average([item.behavior_confidence for item in behaviors]),
        },
        "hotspots": {
            "cameras": [
                _hotspot(camera_id, items)
                for camera_id, items in sorted(
                    camera_groups.items(),
                    key=lambda item: (-len(item[1]), -sum(event.risk_level in {"high", "critical"} for event in item[1])),
                )[:10]
            ],
            "areas": [
                _hotspot(area_id, items)
                for area_id, items in sorted(
                    area_groups.items(),
                    key=lambda item: (-len(item[1]), -sum(event.risk_level in {"high", "critical"} for event in item[1])),
                )[:10]
            ],
        },
        "daily_trend": [
            {
                "date": day,
                "event_total": len(items),
                "high_risk_total": sum(event.risk_level in {"high", "critical"} for event in items),
                "closed_total": sum(event.status == "closed" for event in items),
                "confirmed_total": sum(event.status == "confirmed" for event in items),
                "rejected_total": sum(event.status == "rejected" for event in items),
            }
            for day, items in sorted(daily_groups.items())
        ],
    }


def _count(items: list, key) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in items:
        value = key(item)
        result[value] = result.get(value, 0) + 1
    return result


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _average(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def _hotspot(key: str, events: list[Event]) -> dict:
    return {
        "id": key,
        "event_total": len(events),
        "high_risk_total": sum(event.risk_level in {"high", "critical"} for event in events),
        "closed_total": sum(event.status == "closed" for event in events),
        "avg_duration_minutes": _average([event.duration_seconds / 60 for event in events]),
    }
