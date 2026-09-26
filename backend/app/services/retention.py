"""数据保留清理服务。

运维设计 §3.4：
  - 事件主表  : 90 天
  - 审计日志  : 365 天
  - 模型推理结果 / 时序分类 : 730 天
  - 通知记录  : 365 天
  - 关键帧、训练样本：随事件/事件解释一起清理
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Type

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    AuditLog,
    Event,
    Keyframe,
    ModelResult,
    Notification,
    Review,
    Task,
    TrainingSample,
)


@dataclass
class RetentionResult:
    table: str
    deleted: int


def _delete_older_than(db: Session, model: Type, days: int, timestamp_column: str = "start_time") -> int:
    """删除 model 表中 timestamp_column 早于 (now - days) 的行。"""
    threshold = datetime.utcnow() - timedelta(days=days)
    column = getattr(model, timestamp_column, None)
    if column is None:
        raise ValueError(f"{model.__name__} has no column {timestamp_column}")
    count = db.query(model).filter(column < threshold).delete(synchronize_session=False)
    return count


def run_retention_cleanup(db: Session) -> list[RetentionResult]:
    settings = get_settings()
    results: list[RetentionResult] = []

    # 事件：90 天
    cutoff = datetime.utcnow() - timedelta(days=settings.retention_event_days)
    # 先收集要删的事件 id，再级联清理关联表
    expired_event_ids = [row.id for row in db.query(Event.id).filter(Event.start_time < cutoff).all()]
    if expired_event_ids:
        db.query(TrainingSample).filter(TrainingSample.event_id.in_(expired_event_ids)).delete(synchronize_session=False)
        db.query(Review).filter(Review.event_id.in_(expired_event_ids)).delete(synchronize_session=False)
        db.query(ModelResult).filter(ModelResult.event_id.in_(expired_event_ids)).delete(synchronize_session=False)
        db.query(Keyframe).filter(Keyframe.event_id.in_(expired_event_ids)).delete(synchronize_session=False)
        db.query(Task).filter(Task.event_id.in_(expired_event_ids)).delete(synchronize_session=False)
    results.append(RetentionResult(table="events", deleted=_delete_older_than(db, Event, settings.retention_event_days)))

    # 通知：基于 created_at-like 列（Notification 没有显式 created_at，使用 sent_at/read_at/status）
    notif_cutoff = datetime.utcnow() - timedelta(days=settings.retention_notification_days)
    results.append(
        RetentionResult(
            table="notifications",
            deleted=db.query(Notification)
            .filter(Notification.sent_at < notif_cutoff)
            .delete(synchronize_session=False),
        )
    )

    # 审计日志：基于 created_at
    results.append(
        RetentionResult(
            table="audit_logs",
            deleted=_delete_older_than(db, AuditLog, settings.retention_audit_days, timestamp_column="created_at"),
        )
    )

    # 模型推理结果：基于 created_at
    results.append(
        RetentionResult(
            table="model_results",
            deleted=_delete_older_than(db, ModelResult, settings.retention_metrics_days, timestamp_column="created_at"),
        )
    )

    db.commit()
    return results