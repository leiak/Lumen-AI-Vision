"""审计日志补点测试。"""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.models import Area, Camera, User


def _admin_token(client: TestClient) -> str:
    settings = get_settings()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": settings.default_admin_username, "password": settings.default_admin_password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_login_writes_audit(db_session):
    """成功登录会写入审计日志。"""
    with TestClient(app) as client:
        token = _admin_token(client)
    assert token
    log = db_session.query(User).filter(User.username == get_settings().default_admin_username).first()
    # 至少应当有 login 审计记录
    from app.models import AuditLog
    audits = db_session.query(AuditLog).filter(AuditLog.action == "login").all()
    assert len(audits) >= 1


def test_area_create_writes_audit(db_session):
    camera = Camera(id="cam-audit", name="cam-audit", status="online")
    db_session.add(camera)
    db_session.commit()
    from app.models import AuditLog
    before = db_session.query(AuditLog).filter(AuditLog.action == "create_area").count()

    with TestClient(app) as client:
        token = _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            "/api/v1/areas",
            json={
                "id": "area-audit",
                "camera_id": "cam-audit",
                "name": "test",
                "stay_threshold_seconds": 300,
                "high_risk_seconds": 600,
            },
            headers=headers,
        )
        assert response.status_code == 200

    after = db_session.query(AuditLog).filter(AuditLog.action == "create_area").count()
    assert after > before


def test_review_writes_audit(db_session):
    from app.models import AuditLog, Event, VehicleTrack
    db_session.query(AuditLog).filter(AuditLog.action == "review_event").delete()
    db_session.query(Event).delete()
    db_session.query(VehicleTrack).delete()
    db_session.add(Camera(id="cam-rev", name="cam-rev", status="online"))
    db_session.add(VehicleTrack(id="t-rev", camera_id="cam-rev", area_id="area-rev", start_time=__import__("datetime").datetime.utcnow()))
    event = Event(
        id="evt-rev",
        camera_id="cam-rev",
        area_id="area-rev",
        track_id="t-rev",
        event_type="abnormal_stay",
        risk_level="medium",
        start_time=__import__("datetime").datetime.utcnow(),
        duration_seconds=120,
        status="candidate",
    )
    db_session.add(event)
    db_session.commit()

    with TestClient(app) as client:
        token = _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            "/api/v1/events/evt-rev/review",
            json={
                "reviewer_id": "admin-id",
                "result": "abnormal",
                "comment": "ok",
                "corrected_event_type": "abnormal_stay",
                "corrected_risk_level": "high",
            },
            headers=headers,
        )
        assert response.status_code == 200

    log = db_session.query(AuditLog).filter(AuditLog.action == "review_event", AuditLog.resource_id == "evt-rev").first()
    assert log is not None
    assert log.after_value["result"] == "abnormal"