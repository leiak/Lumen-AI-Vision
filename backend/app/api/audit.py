from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_roles
from app.models import AuditLog, User

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit"])


@router.get("")
def list_audit_logs(
    resource_type: str | None = None,
    resource_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
) -> list[dict]:
    query = db.query(AuditLog)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if resource_id:
        query = query.filter(AuditLog.resource_id == resource_id)
    return [
        {
            "id": item.id,
            "user_id": item.user_id,
            "action": item.action,
            "resource_type": item.resource_type,
            "resource_id": item.resource_id,
            "created_at": item.created_at,
        }
        for item in query.order_by(AuditLog.created_at.desc()).limit(200).all()
    ]
