"""任务升级服务。

按运维设计 §3.3：
  high  → due_at 超时后升级到仓储主管（supervisor）
  critical → due_at 超时后同时通知值班管理员（duty_admin）+ 运营负责人（ops_lead）
同一事件在同一升级窗口内不重复通知相同角色。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Event, Notification, Task, User
from app.services.notification_service import dispatch_notification


@dataclass(frozen=True)
class EscalationPlan:
    next_level: int
    roles: tuple[str, ...]


# 升级路径：当前等级 → 下一等级的目标角色
_ESCALATION_LADDER = {
    "high": [
        EscalationPlan(next_level=1, roles=("supervisor",)),
    ],
    "critical": [
        EscalationPlan(next_level=1, roles=("duty_admin",)),
        EscalationPlan(next_level=2, roles=("supervisor", "ops_lead")),
    ],
}


def _pick_users_by_role(db: Session, role: str, limit: int = 5) -> list[User]:
    return (
        db.query(User)
        .filter(User.is_active.is_(True), User.role == role)
        .order_by(User.created_at)
        .limit(limit)
        .all()
    )


def _already_notified(db: Session, task_id: str, role: str, level: int) -> bool:
    """检查同一窗口是否已经通知过该角色。"""
    existing = (
        db.query(Notification)
        .filter(
            Notification.task_id == task_id,
            Notification.receiver_role == role,
            Notification.escalation_level == level,
        )
        .first()
    )
    return existing is not None


def escalate_overdue_tasks(db: Session, now: datetime | None = None) -> list[Task]:
    """遍历超时任务，按风险等级执行升级，返回已升级的任务列表。"""
    now = now or datetime.utcnow()
    overdue_tasks = db.query(Task).filter(Task.status == "pending", Task.due_at < now).all()
    upgraded: list[Task] = []
    for task in overdue_tasks:
        event = db.get(Event, task.event_id)
        if not event:
            continue
        ladder = _ESCALATION_LADDER.get(event.risk_level, [])
        if not ladder:
            # 普通 medium 任务只标记为 escalated，不增加新通知
            task.status = "escalated"
            upgraded.append(task)
            continue
        current_level = task.escalation_level
        next_plan = next((plan for plan in ladder if plan.next_level == current_level + 1), None)
        if next_plan is None:
            # 已超过该风险等级的最大升级次数
            task.status = "escalated"
            upgraded.append(task)
            continue
        dispatched_any = False
        for role in next_plan.roles:
            if _already_notified(db, task.id, role, next_plan.next_level):
                continue
            users = _pick_users_by_role(db, role)
            actual_role = role
            if not users:
                # 角色无在职用户，回退到 admin 兜底
                users = _pick_users_by_role(db, "admin")
                actual_role = "admin" if users else role
            if not users:
                continue
            for user in users:
                notification = Notification(
                    id=f"ntf-{uuid.uuid4().hex[:12]}",
                    event_id=task.event_id,
                    task_id=task.id,
                    receiver_id=user.id,
                    receiver_role=actual_role,
                    channel="in_app",
                    status="pending",
                    retry_count=0,
                    escalation_level=next_plan.next_level,
                )
                db.add(notification)
                dispatch_notification(
                    db,
                    notification,
                    (
                        f"事件 {task.event_id} 已超时，"
                        f"风险等级 {event.risk_level}，请 {role} 立即介入。"
                    ),
                )
                dispatched_any = True
        task.escalation_level = next_plan.next_level
        task.status = "escalated"
        upgraded.append(task)
        if dispatched_any:
            db.add(
                _audit_entry(
                    user_id="system",
                    action="escalate_task",
                    resource_type="task",
                    resource_id=task.id,
                    after_value={"escalation_level": next_plan.next_level, "roles": list(next_plan.roles)},
                )
            )
    db.commit()
    return upgraded


def _audit_entry(*, user_id: str, action: str, resource_type: str, resource_id: str, before=None, after_value=None):
    from app.models import AuditLog

    return AuditLog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before_value=before,
        after_value=after_value,
    )