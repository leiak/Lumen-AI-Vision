"""CSV 数据导出端点（运维设计 §3.5）。

支持：
  - GET /api/v1/exports/events          事件列表（管理员/操作员）
  - GET /api/v1/exports/audit-logs      审计日志（仅管理员）
  - GET /api/v1/exports/metrics         模型推理结果（管理员/操作员）

CSV 中文表头与 RFC4180 兼容；时间戳 ISO8601。
"""

import csv
import io
from datetime import datetime
from typing import Iterable

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models import AuditLog, Event, ModelResult, User


router = APIRouter(prefix="/api/v1/exports", tags=["exports"])


def _csv_response(rows: Iterable[dict], filename: str) -> StreamingResponse:
    """构造 CSV 流式响应（避免一次性加载全表到内存）。"""
    iterator = iter(rows)
    try:
        first = next(iterator)
    except StopIteration:
        # 空表：返回只有表头
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([])
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    rows_iter = iter([first, *iterator])

    def stream() -> Iterable[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(list(first.keys()))
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        for row in rows_iter:
            writer.writerow([row.get(column, "") for column in first.keys()])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    return StreamingResponse(
        stream(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/events")
def export_events(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "operator")),
) -> StreamingResponse:
    events = db.query(Event).order_by(Event.start_time.desc()).limit(10000).all()
    rows = [
        {
            "id": event.id,
            "camera_id": event.camera_id,
            "area_id": event.area_id,
            "track_id": event.track_id,
            "event_type": event.event_type,
            "risk_level": event.risk_level,
            "status": event.status,
            "start_time": event.start_time.isoformat() if event.start_time else "",
            "duration_seconds": event.duration_seconds,
            "summary": event.summary or "",
        }
        for event in events
    ]
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return _csv_response(rows, f"events-{timestamp}.csv")


@router.get("/audit-logs")
def export_audit_logs(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin")),
) -> StreamingResponse:
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(50000).all()
    rows = [
        {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "ip": log.ip or "",
            "created_at": log.created_at.isoformat() if log.created_at else "",
        }
        for log in logs
    ]
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return _csv_response(rows, f"audit-logs-{timestamp}.csv")


@router.get("/metrics")
def export_metrics(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "operator")),
) -> StreamingResponse:
    results = db.query(ModelResult).order_by(ModelResult.created_at.desc()).limit(20000).all()
    rows = [
        {
            "id": result.id,
            "event_id": result.event_id,
            "model_name": result.model_name,
            "model_version": result.model_version,
            "model_type": result.model_type,
            "label": result.label,
            "score": result.score,
            "latency_ms": result.latency_ms,
            "created_at": result.created_at.isoformat() if result.created_at else "",
        }
        for result in results
    ]
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return _csv_response(rows, f"metrics-{timestamp}.csv")