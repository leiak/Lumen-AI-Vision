"""通知渠道 + 未读计数 端点测试。"""

import uuid
from datetime import datetime

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.models import Notification, User
from app.services.notification_service import dispatch_notification


def _bootstrap_admin() -> None:
    """触发应用启动事件，确保默认管理员用户存在。"""
    with TestClient(app) as client:
        settings = get_settings()
        # 如果 startup 已运行且 admin 已被测试删掉，这里手动重建
        from app.core.database import SessionLocal
        from app.core.security import hash_password
        from app.models import User
        sess = SessionLocal()
        try:
            existing = sess.query(User).filter(User.username == settings.default_admin_username).first()
            if not existing:
                sess.add(User(
                    id="00000000-0000-0000-0000-000000000001",
                    username=settings.default_admin_username,
                    hashed_password=hash_password(settings.default_admin_password),
                    full_name="System Admin",
                    role=settings.default_admin_role,
                ))
                sess.commit()
        finally:
            sess.close()
        response = client.post(
            "/api/v1/auth/login",
            json={"username": settings.default_admin_username, "password": settings.default_admin_password},
        )
        print("DEBUG bootstrap login status=", response.status_code)


def _admin_token(client: TestClient) -> str:
    settings = get_settings()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": settings.default_admin_username, "password": settings.default_admin_password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _system_admin(db_session) -> User:
    """获取启动时创建的系统管理员（id 固定）。"""
    _bootstrap_admin()
    settings = get_settings()
    admin = db_session.query(User).filter(User.username == settings.default_admin_username).first()
    assert admin is not None, "system admin must exist"
    return admin


def test_in_app_dispatch_marks_sent(db_session):
    """in_app 渠道不应触发外部调用；写入即视为已送达。"""
    admin = _system_admin(db_session)
    notif = Notification(
        id="notif-in-app",
        receiver_id=admin.id,
        event_id="00000000-0000-0000-0000-000000000000",
        task_id=None,
        channel="in_app",
        status="pending",
        retry_count=0,
    )
    db_session.add(notif)
    db_session.commit()

    result = dispatch_notification(db_session, notif, "hello in-app")
    assert result.status == "sent"
    assert result.sent_at is not None
    assert result.retry_count == 1


def test_unread_count_endpoint(db_session):
    """未读计数只统计 in_app + 非 read 的通知。"""
    admin = _system_admin(db_session)
    # 隔离状态：清空 admin 的既有通知
    db_session.query(Notification).filter(Notification.receiver_id == admin.id).delete()
    # 真实事件（Notification.event_id 是 FK 到 events.id）
    from app.models import Camera, Event, Area
    from datetime import datetime as _dt
    if not db_session.get(Camera, "cam-unread"):
        db_session.add(Camera(id="cam-unread", name="cam-unread", status="online"))
    if not db_session.get(Area, "area-unread"):
        db_session.add(Area(id="area-unread", camera_id="cam-unread", name="a",
                            stay_threshold_seconds=120, high_risk_seconds=600))
    if not db_session.get(Event, "evt-unread"):
        db_session.add(Event(id="evt-unread", camera_id="cam-unread", area_id="area-unread",
                             track_id="tr-unread", event_type="abnormal_stay",
                             risk_level="medium", start_time=_dt.utcnow(),
                             duration_seconds=300, status="candidate"))
    db_session.commit()

    db_session.add_all([
        Notification(id=str(uuid.uuid4()), receiver_id=admin.id, event_id="evt-unread",
                     channel="in_app", status="pending"),
        Notification(id=str(uuid.uuid4()), receiver_id=admin.id, event_id="evt-unread",
                     channel="in_app", status="pending"),
        Notification(id=str(uuid.uuid4()), receiver_id=admin.id, event_id="evt-unread",
                     channel="webhook", status="sent"),
        Notification(id=str(uuid.uuid4()), receiver_id=admin.id, event_id="evt-unread",
                     channel="in_app", status="read", read_at=datetime.utcnow()),
    ])
    db_session.commit()

    with TestClient(app) as client:
        token = _admin_token(client)
        response = client.get(
            "/api/v1/notifications/unread-count",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    body = response.json()
    # 本测试向 system admin 新增了 2 条 in_app + pending 通知
    assert body["unread"] == 2


def test_unsupported_channel_marks_failed(db_session):
    admin = _system_admin(db_session)
    notif = Notification(
        id="notif-bad",
        receiver_id=admin.id,
        event_id="00000000-0000-0000-0000-000000000000",
        channel="pigeon",
        status="pending",
    )
    db_session.add(notif)
    db_session.commit()

    result = dispatch_notification(db_session, notif, "hi")
    assert result.status == "failed"
    assert result.retry_count == 1