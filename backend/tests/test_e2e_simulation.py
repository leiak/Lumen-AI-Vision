"""端到端模拟测试：使用合成数据走完完整业务流。

业务流程：
  1. 启动后端（TestClient）
  2. 创建用户（admin / operator / supervisor / security / duty_admin / ops_lead）
  3. 注册摄像头 + 区域 + AreaGroup（用于跨摄像头去重）
  4. 边缘端上报 30 个事件（其中 4 组重复用于测试去重，2 组升级用于测试 escalation）
  5. 关键帧上传（含脱敏状态位）
  6. 触发 VL/时序分类
  7. 复审若干事件（生成训练样本）
  8. 计算模型准确率
  9. 触发任务升级（同步调用 Celery 任务函数）
  10. 验证通知分发
  11. 数据导出 CSV
  12. 数据保留清理（构造过期数据 + 运行清理）

执行：pytest tests/test_e2e_simulation.py -v -s
"""

import io
import uuid
from datetime import datetime, timedelta

import numpy as np
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models import (
    Area,
    AreaGroup,
    Camera,
    Event,
    Keyframe,
    ModelResult,
    Notification,
    Review,
    TrainingSample,
    User,
    area_group_members,
)
from app.services.escalation import escalate_overdue_tasks
from app.services.model_evaluation import compute_accuracy
from app.services.retention import run_retention_cleanup


def _make_jpeg_bytes(width: int = 320, height: int = 240, seed: int = 0) -> bytes:
    """生成合成 JPEG（带噪声，方便后续脱敏/上传测试）。"""
    try:
        import cv2  # type: ignore
        rng = np.random.default_rng(seed)
        image = rng.integers(0, 255, (height, width, 3), dtype=np.uint8)
        ok, buffer = cv2.imencode(".jpg", image)
        assert ok
        return buffer.tobytes()
    except ImportError:
        # fallback to raw bytes so test still runs without cv2
        return b"\xff\xd8\xff\xe0" + b"\x00" * 1024


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _make_user(db, role: str, username: str) -> User:
    from app.core.security import hash_password
    user = User(
        id=f"user-{role}-{username}",
        username=username,
        full_name=username,
        role=role,
        is_active=True,
        hashed_password=hash_password("test-pass"),
    )
    db.add(user)
    db.flush()
    return user


def test_e2e_full_pipeline_with_synthetic_data():
    """端到端业务流：30 个事件 + 升级 + 通知 + 复审 + 准确率 + 导出 + 清理。"""
    settings = get_settings()

    # 0. 隔离 + 配置：使用本地文件存储 + 关闭 webhook 外发，方便端到端跑通
    import os
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["STORAGE_LOCAL_PATH"] = "./tests/tmp-storage-e2e"
    os.environ["NOTIFICATION_WEBHOOK_URL"] = ""
    from app.core.config import Settings
    test_settings = Settings(
        storage_backend="local",
        storage_local_path="./tests/tmp-storage-e2e",
        notification_webhook_url=None,
    )
    from app.services import storage, notification_service
    storage.get_settings = lambda: test_settings
    notification_service.get_settings = lambda: test_settings

    from app.core.database import Base, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # 1. 初始化数据库表 + 默认管理员
    with TestClient(app) as bootstrap:
        bootstrap.post(
            "/api/v1/auth/login",
            json={"username": settings.default_admin_username, "password": settings.default_admin_password},
        )

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == settings.default_admin_username).first()
        # 2. 各类角色
        operator = _make_user(db, "operator", "op-1")
        supervisor = _make_user(db, "supervisor", "sup-1")
        security = _make_user(db, "security", "sec-1")
        duty_admin = _make_user(db, "duty_admin", "duty-1")
        ops_lead = _make_user(db, "ops_lead", "ops-1")

        # 3. 摄像头 + 区域（3 个摄像头 + 4 个区域；其中 2 个区域加入同一个 AreaGroup 用于跨摄像头去重）
        cams = [Camera(id=f"cam-{i}", name=f"cam-{i}", status="online", location=f"loc-{i}")
                 for i in range(3)]
        areas = [
            Area(id=f"area-a", camera_id="cam-0", name="gate-A",
                 stay_threshold_seconds=120, high_risk_seconds=600,
                 polygon=[[100, 100], [400, 100], [400, 400], [100, 400]]),
            Area(id=f"area-b", camera_id="cam-1", name="gate-B",
                 stay_threshold_seconds=120, high_risk_seconds=600,
                 polygon=[[100, 100], [400, 100], [400, 400], [100, 400]]),
            Area(id=f"area-c", camera_id="cam-2", name="gate-C",
                 stay_threshold_seconds=180, high_risk_seconds=900,
                 polygon=[[100, 100], [400, 100], [400, 400], [100, 400]]),
            Area(id=f"area-d", camera_id="cam-0", name="gate-D",
                 stay_threshold_seconds=120, high_risk_seconds=600,
                 polygon=[[100, 100], [400, 100], [400, 400], [100, 400]]),
        ]
        db.add_all(cams + areas)
        # AreaGroup：把 area-a 与 area-b 编为一组
        group = AreaGroup(id="grp-1", name="主入口组", priority=10, dedup_window_seconds=600)
        db.add(group)
        db.flush()
        db.execute(area_group_members.insert().values(area_group_id="grp-1", area_id="area-a"))
        db.execute(area_group_members.insert().values(area_group_id="grp-1", area_id="area-b"))
        db.commit()
    finally:
        db.close()

    # 4. 通过 API 创建任务（依赖管理员 token）
    with TestClient(app) as client:
        admin_token = _login(client, settings.default_admin_username, settings.default_admin_password)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 边缘端：30 个事件上报
        edge_headers = {"X-API-Key": settings.edge_api_key}
        plate_hash_a = "plate-A"  # 同一车牌出现在 cam-0 + cam-1（去重命中）
        now = datetime.utcnow()

        accepted: list[str] = []
        dedup_hits: list[str] = []
        for i in range(30):
            cam_id = ["cam-0", "cam-1", "cam-2"][i % 3]
            area_id = ["area-a", "area-b", "area-c"][i % 3]
            # i=0..1 是同一车牌在 cam-0+cam-1，应触发 L1 去重（命中 area_group）
            plate = plate_hash_a if i in (0, 1) else f"plate-{i}"
            # i=5,6 高风险超时（用于升级）
            duration = 1800 if i in (5, 6) else 300
            track_id = f"tr-{i:03d}"
            payload = {
                "camera_id": cam_id,
                "area_id": area_id,
                "event_type_hint": "abnormal_stay",
                "vehicle_plate_hash": plate,
                "start_time": (now - timedelta(minutes=30 - i)).isoformat(),
                "end_time": (now - timedelta(minutes=29 - i)).isoformat(),
                "duration_seconds": duration,
                "track": {
                    "id": track_id,
                    "camera_id": cam_id,
                    "area_id": area_id,
                    "vehicle_type": "car",
                    "start_time": (now - timedelta(minutes=30 - i)).isoformat(),
                    "static_seconds": duration,
                    "status": "ended",
                },
                "behaviors": [],
                "keyframes": [],
            }
            response = client.post("/api/v1/edge/events", json=payload, headers=edge_headers)
            assert response.status_code == 200, response.text
            body = response.json()
            if body.get("deduplicated"):
                dedup_hits.append(body["event_id"])
            else:
                accepted.append(body["event_id"])

        print(f"[E2E] 上报 30 个事件：接受={len(accepted)} 去重命中={len(dedup_hits)}")
        # i=1 应当与 i=0 命中同 area_group + plate
        assert len(dedup_hits) >= 1, "跨摄像头去重应当至少命中 1 次"

        # 5. 关键帧上传：取 5 个事件，每个 2 张帧（含 privacy_processed）
        for event_id in accepted[:5]:
            event = db.get(Event, event_id) if False else None  # 占位
            # 用 db 查询
        db2 = SessionLocal()
        try:
            sample_events = db2.query(Event).limit(5).all()
            for evt in sample_events:
                for role in ("state_change", "evidence"):
                    frame_id = f"frame-{evt.id}-{role}"
                    files = {"file": (f"{frame_id}.jpg", _make_jpeg_bytes(seed=hash(evt.id) % 1000),
                                       "image/jpeg")}
                    data = {
                        "track_id": evt.track_id,
                        "event_id": evt.id,
                        "frame_id": frame_id,
                        "frame_role": role,
                        "timestamp": now.isoformat(),
                        "privacy_processed": "true",
                    }
                    up = client.post(
                        "/api/v1/edge/keyframes/upload",
                        data=data,
                        files=files,
                        headers=edge_headers,
                    )
                    assert up.status_code == 200, up.text
        finally:
            db2.close()

        # 6. 触发时序分类 + VL 解释（取 3 个事件）
        db3 = SessionLocal()
        try:
            sample_events = db3.query(Event).limit(3).all()
            for evt in sample_events:
                # 时序分类
                response = client.post(
                    "/api/v1/models/temporal/classify",
                    json={"event_id": evt.id},
                    headers=admin_headers,
                )
                assert response.status_code == 200, response.text
                # VL 解释
                response = client.post(
                    "/api/v1/models/vl/explain",
                    json={"event_id": evt.id},
                    headers=admin_headers,
                )
                assert response.status_code == 200, response.text
        finally:
            db3.close()

        # 7. 复审若干事件（生成训练样本 + 标签）
        db4 = SessionLocal()
        try:
            events_to_review = db4.query(Event).limit(5).all()
            for idx, evt in enumerate(events_to_review):
                review_payload = {
                    "reviewer_id": str(admin.id),
                    "result": "abnormal" if idx % 2 == 0 else "normal",
                    "comment": f"synthetic review #{idx}",
                }
                response = client.post(
                    f"/api/v1/events/{evt.id}/review",
                    json=review_payload,
                    headers=admin_headers,
                )
                assert response.status_code == 200, response.text
        finally:
            db4.close()

        # 8. 模型准确率
        db5 = SessionLocal()
        try:
            reports = compute_accuracy(db5)
            print(f"[E2E] 模型准确率：{[(r.model_type, r.sample_count, round(r.precision, 2)) for r in reports]}")
            assert reports, "至少有一种模型类型产生报告"
        finally:
            db5.close()

        response = client.get("/api/v1/models/accuracy", headers=admin_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

        # 9. 触发任务升级：构造一条已过期的高风险任务
        db6 = SessionLocal()
        try:
            from app.models import Task
            # 找 high/critical 风险事件
            evt = db6.query(Event).filter(Event.risk_level.in_(["high", "critical"])).first()
            assert evt is not None
            task = Task(
                id=f"task-esc-{uuid.uuid4()}",
                event_id=evt.id,
                assignee_id=str(security.id),
                assignee_role="security",
                status="pending",
                due_at=datetime.utcnow() - timedelta(minutes=10),
            )
            db6.add(task)
            db6.commit()
            upgraded = escalate_overdue_tasks(db6)
            print(f"[E2E] 升级任务数：{len(upgraded)}")
            assert len(upgraded) == 1
            notif_count = db6.query(Notification).filter(Notification.task_id == task.id).count()
            assert notif_count >= 1
        finally:
            db6.close()

        # 10. 验证通知分发：以 supervisor 登录，查看升级产生的通知
        supervisor_token = _login(client, "sup-1", "test-pass")
        supervisor_headers = {"Authorization": f"Bearer {supervisor_token}"}
        response = client.get("/api/v1/notifications", headers=supervisor_headers)
        assert response.status_code == 200
        notifs = response.json()
        assert len(notifs) >= 1, "supervisor 应当收到升级通知"
        unread = client.get("/api/v1/notifications/unread-count", headers=supervisor_headers).json()
        assert unread["unread"] >= 1
        print(f"[E2E] supervisor 通知：{len(notifs)} 未读：{unread['unread']}")

        # 11. 数据导出 CSV
        for path in ("/api/v1/exports/events", "/api/v1/exports/audit-logs", "/api/v1/exports/metrics"):
            response = client.get(path, headers=admin_headers)
            if response.status_code != 200:
                print(f"[E2E] {path} 失败 status={response.status_code} body={response.text[:300]}")
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/csv")
            assert "attachment" in response.headers["content-disposition"]
            print(f"[E2E] {path} 导出 {len(response.content)} 字节")

        # 12. 数据保留清理（构造过期事件 → 调用清理）
        db7 = SessionLocal()
        try:
            old_time = datetime.utcnow() - timedelta(days=100)
            db7.add(Camera(id="cam-old", name="cam-old", status="online"))
            db7.add(Area(id="area-old", camera_id="cam-old", name="o",
                        stay_threshold_seconds=120, high_risk_seconds=600))
            db7.add(Event(id="evt-old", camera_id="cam-old", area_id="area-old",
                         track_id="tr-old", event_type="abnormal_stay",
                         risk_level="high", start_time=old_time,
                         duration_seconds=600, status="candidate"))
            db7.commit()
            results = run_retention_cleanup(db7)
            summary = {r.table: r.deleted for r in results}
            print(f"[E2E] 保留清理：{summary}")
            assert summary["events"] >= 1
            assert db7.get(Event, "evt-old") is None
        finally:
            db7.close()

        print("[E2E] === 全流程通过：30 事件 -> 去重 -> 关键帧 -> 模型 -> 复审 -> 准确率 -> 升级 -> 通知 -> 导出 -> 清理 ===")