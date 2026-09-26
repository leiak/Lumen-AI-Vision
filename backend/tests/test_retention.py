"""数据保留清理测试。"""

import uuid
from datetime import datetime, timedelta

from app.core.database import SessionLocal
from app.core.config import get_settings
from app.main import app
from app.models import (
    Area,
    AuditLog,
    Camera,
    Event,
    Keyframe,
    ModelResult,
    Notification,
    Review,
    Task,
    TrainingSample,
    User,
)
from app.services.retention import run_retention_cleanup


def _user(db, role="admin", username="admin-x") -> User:
    u = User(
        id=f"user-{role}-{username}",
        username=username,
        full_name=username,
        role=role,
        is_active=True,
        hashed_password="x",
    )
    db.add(u)
    db.flush()
    return u


def test_retention_deletes_expired_events_and_cascades(db_session):
    """事件超过 90 天：级联清理任务/关键帧/模型结果/复审/训练样本。"""
    _user(db_session)
    db_session.add(Camera(id="cam-ret", name="cam-ret", status="online"))
    db_session.add(Area(id="area-ret", camera_id="cam-ret", name="a",
                        stay_threshold_seconds=120, high_risk_seconds=600))

    old = datetime.utcnow() - timedelta(days=100)
    fresh = datetime.utcnow() - timedelta(days=10)
    e_old = Event(id="evt-old", camera_id="cam-ret", area_id="area-ret",
                  track_id="tr-old", event_type="abnormal_stay",
                  risk_level="high", start_time=old, duration_seconds=300, status="candidate")
    e_fresh = Event(id="evt-fresh", camera_id="cam-ret", area_id="area-ret",
                    track_id="tr-fresh", event_type="abnormal_stay",
                    risk_level="medium", start_time=fresh, duration_seconds=300, status="candidate")
    db_session.add_all([e_old, e_fresh])
    db_session.flush()

    db_session.add_all([
        Task(id="t-old", event_id="evt-old", assignee_id="user-admin-admin-x",
             assignee_role="admin", status="pending", due_at=old),
        Keyframe(id=str(uuid.uuid4()), track_id="tr-old", event_id="evt-old",
                 storage_url="local://x", timestamp=old, privacy_processed=True),
        ModelResult(id=str(uuid.uuid4()), event_id="evt-old", model_name="m",
                    model_version="v", model_type="vl", label="x", score=0.5,
                    output={}, latency_ms=10, created_at=old),
    ])
    db_session.commit()

    results = run_retention_cleanup(db_session)
    summary = {r.table: r.deleted for r in results}
    assert summary["events"] == 1
    assert db_session.query(Event).filter(Event.id == "evt-old").first() is None
    assert db_session.query(Event).filter(Event.id == "evt-fresh").first() is not None
    assert db_session.query(Task).filter(Task.event_id == "evt-old").count() == 0
    assert db_session.query(Keyframe).filter(Keyframe.event_id == "evt-old").count() == 0
    assert db_session.query(ModelResult).filter(ModelResult.event_id == "evt-old").count() == 0


def test_retention_deletes_old_notifications_and_audit(db_session):
    """通知与审计超过各自保留期被清掉。"""
    settings = get_settings()
    old = datetime.utcnow() - timedelta(days=settings.retention_notification_days + 5)
    db_session.add(Notification(id="n-old", receiver_id="u", event_id="e",
                                channel="in_app", status="sent", sent_at=old))
    db_session.add(Notification(id="n-new", receiver_id="u", event_id="e",
                                channel="in_app", status="sent",
                                sent_at=datetime.utcnow()))
    db_session.add(AuditLog(id="a-old", user_id="u", action="login",
                            resource_type="auth", resource_id="u", created_at=old))
    db_session.commit()

    results = run_retention_cleanup(db_session)
    summary = {r.table: r.deleted for r in results}
    assert summary["notifications"] >= 1
    assert summary["audit_logs"] >= 1
    assert db_session.query(Notification).filter(Notification.id == "n-old").first() is None
    assert db_session.query(Notification).filter(Notification.id == "n-new").first() is not None


def test_retention_keeps_fresh_data(db_session):
    """新数据不应被误删。"""
    now = datetime.utcnow()
    db_session.add(Camera(id="cam-fresh", name="cam-fresh", status="online"))
    db_session.add(Area(id="area-fresh", camera_id="cam-fresh", name="a",
                        stay_threshold_seconds=120, high_risk_seconds=600))
    db_session.add(Event(id="evt-keep", camera_id="cam-fresh", area_id="area-fresh",
                         track_id="tr-keep", event_type="abnormal_stay",
                         risk_level="low", start_time=now, duration_seconds=100, status="candidate"))
    db_session.commit()

    results = run_retention_cleanup(db_session)
    summary = {r.table: r.deleted for r in results}
    assert summary["events"] == 0
    assert db_session.query(Event).filter(Event.id == "evt-keep").first() is not None