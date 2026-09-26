"""模型准确率统计测试。"""

import uuid
from datetime import datetime

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.models import (
    Area,
    Camera,
    Event,
    ModelResult,
    Review,
    TrainingSample,
    User,
)
from app.services.model_evaluation import compute_accuracy


def _bootstrap_admin() -> None:
    with TestClient(app) as client:
        settings = get_settings()
        client.post(
            "/api/v1/auth/login",
            json={"username": settings.default_admin_username, "password": settings.default_admin_password},
        )


def _system_admin(db) -> User:
    _bootstrap_admin()
    settings = get_settings()
    admin = db.query(User).filter(User.username == settings.default_admin_username).first()
    assert admin is not None
    return admin


def _build_event(db, camera_id="cam-acc", area_id="area-acc") -> Event:
    if not db.get(Camera, camera_id):
        db.add(Camera(id=camera_id, name=camera_id, status="online"))
    if not db.get(Area, area_id):
        db.add(Area(id=area_id, camera_id=camera_id, name=area_id,
                    stay_threshold_seconds=120, high_risk_seconds=600))
    event = Event(
        id=f"evt-{uuid.uuid4()}",
        camera_id=camera_id,
        area_id=area_id,
        track_id=f"tr-{uuid.uuid4()}",
        event_type="abnormal_stay",
        risk_level="medium",
        start_time=datetime.utcnow(),
        duration_seconds=300,
        status="candidate",
    )
    db.add(event)
    db.flush()
    return event


def _build_review_sample(db, event_id, label):
    review = Review(id=str(uuid.uuid4()), event_id=event_id,
                     reviewer_id="r", result=label, comment="c")
    db.add(review)
    db.flush()
    sample = TrainingSample(
        id=str(uuid.uuid4()),
        event_id=event_id,
        review_id=review.id,
        label=label,
        risk_level="medium",
        reviewer_id="r",
    )
    db.add(sample)
    db.flush()


def test_compute_accuracy_per_model_type(db_session):
    """temporal 模型：2 个 abnormal_stay + 1 个 normal_stay，groundtruth 全 abnormal → precision=2/2, recall=2/2。
    vl 模型：1 个 event_explanation，groundtruth abnormal → 不参与正样本判定（fp=1）。
    """
    # 隔离：清理之前测试遗留的样本，避免混入统计
    db_session.query(TrainingSample).delete()
    db_session.query(Review).delete()
    db_session.query(ModelResult).delete()
    db_session.commit()
    admin = _system_admin(db_session)
    e1 = _build_event(db_session, "cam-acc", "area-acc")
    e2 = _build_event(db_session, "cam-acc", "area-acc")
    e3 = _build_event(db_session, "cam-acc", "area-acc")

    db_session.add_all([
        ModelResult(id=str(uuid.uuid4()), event_id=e1.id, model_name="m", model_version="v",
                    model_type="temporal", label="abnormal_stay", score=0.9, output={}, latency_ms=10),
        ModelResult(id=str(uuid.uuid4()), event_id=e2.id, model_name="m", model_version="v",
                    model_type="temporal", label="abnormal_stay", score=0.7, output={}, latency_ms=10),
        ModelResult(id=str(uuid.uuid4()), event_id=e3.id, model_name="m", model_version="v",
                    model_type="temporal", label="normal_stay", score=0.6, output={}, latency_ms=10),
        ModelResult(id=str(uuid.uuid4()), event_id=e1.id, model_name="m", model_version="v",
                    model_type="vl", label="event_explanation", score=0.8, output={}, latency_ms=10),
    ])
    for event in (e1, e2, e3):
        _build_review_sample(db_session, event.id, "abnormal")
    db_session.commit()

    reports = {report.model_type: report for report in compute_accuracy(db_session)}
    assert "temporal" in reports
    temporal = reports["temporal"]
    assert temporal.sample_count == 3
    assert temporal.true_positive == 2
    assert temporal.false_negative == 1
    assert temporal.precision == 1.0
    assert temporal.recall == 2 / 3
    assert "vl" in reports


def test_compute_accuracy_handles_empty(db_session):
    """没有任何复核样本时返回空列表。"""
    _bootstrap_admin()
    # 清理既有 TrainingSample 以避免上一个测试残留
    db_session.query(TrainingSample).delete()
    db_session.commit()
    assert compute_accuracy(db_session) == []


def test_model_accuracy_endpoint(client_with_admin):
    client, headers = client_with_admin
    response = client.get("/api/v1/models/accuracy", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)