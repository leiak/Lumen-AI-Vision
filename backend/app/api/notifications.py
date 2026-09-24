from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.metrics import NOTIFICATION_READS
from app.models import Notification, User
from app.schemas import NotificationRead

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.receiver_id == current_user.id)
        .order_by(Notification.id.desc())
        .all()
    )


@router.post("/{notification_id}/read", response_model=NotificationRead)
def mark_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Notification:
    notification = db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="notification not found")
    if notification.receiver_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="permission denied")
    notification.status = "read"
    notification.read_at = datetime.utcnow()
    db.commit()
    NOTIFICATION_READS.labels(mode="single").inc()
    db.refresh(notification)
    return notification


@router.post("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    notifications = (
        db.query(Notification)
        .filter(Notification.receiver_id == current_user.id, Notification.status != "read")
        .all()
    )
    now = datetime.utcnow()
    for notification in notifications:
        notification.status = "read"
        notification.read_at = now
    db.commit()
    NOTIFICATION_READS.labels(mode="batch").inc(len(notifications))
    return {"updated": len(notifications)}
