import uuid
from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.core.config import get_settings


def test_camera_area_event_review_flow() -> None:
    with TestClient(app) as client:
        settings = get_settings()
        token_response = client.post(
            "/api/v1/auth/login",
            json={"username": settings.default_admin_username, "password": settings.default_admin_password},
        )
        assert token_response.status_code == 200
        token = token_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        edge_headers = {"X-API-Key": settings.edge_api_key}
        camera_id = str(uuid.uuid4())
        area_id = str(uuid.uuid4())
        track_id = str(uuid.uuid4())

        assert client.post("/api/v1/cameras", json={"id": camera_id, "name": "库门口"}, headers=headers).status_code == 200
        assert client.post(
            "/api/v1/areas",
            json={
                "id": area_id,
                "camera_id": camera_id,
                "name": "库门口",
                "stay_threshold_seconds": 300,
                "high_risk_seconds": 600,
            },
            headers=headers,
        ).status_code == 200

        event_payload = {
            "camera_id": camera_id,
            "area_id": area_id,
            "track": {
                "id": track_id,
                "camera_id": camera_id,
                "area_id": area_id,
                "start_time": "2026-09-23T10:00:00",
                "status": "static",
                "static_seconds": 330,
            },
            "event_type_hint": "abnormal_stay",
            "start_time": "2026-09-23T10:00:00",
            "duration_seconds": 330,
            "keyframes": [
                {
                    "id": str(uuid.uuid4()),
                    "timestamp": "2026-09-23T10:00:01",
                    "storage_url": "local://frame.jpg",
                }
            ],
        }
        response = client.post("/api/v1/edge/events", json=event_payload, headers=edge_headers)
        assert response.status_code == 200
        event_id = response.json()["event_id"]

        assert client.get(f"/api/v1/events/{event_id}", headers=headers).status_code == 200
        assert client.get(f"/api/v1/events/{event_id}/keyframes", headers=headers).status_code == 200
        review_response = client.post(
            f"/api/v1/events/{event_id}/review",
            json={
                "reviewer_id": str(uuid.uuid4()),
                "result": "abnormal",
                "comment": "货车异常停留",
            },
            headers=headers,
        )
        assert review_response.status_code == 200
        assert client.get(f"/api/v1/events/{event_id}", headers=headers).json()["status"] == "confirmed"
        assert client.post(
            "/api/v1/models/temporal/classify",
            json={"event_id": event_id},
            headers=headers,
        ).status_code == 200
        assert client.post(
            "/api/v1/models/vl/explain",
            json={"event_id": event_id},
            headers=headers,
        ).status_code == 200
        assert client.get("/api/v1/tasks", headers=headers).status_code == 200
        assert client.get("/api/v1/notifications", headers=headers).status_code == 200
        assert client.get("/api/v1/metrics/summary", headers=headers).status_code == 200


def test_admin_management_and_low_risk_edge_event() -> None:
    with TestClient(app) as client:
        settings = get_settings()
        login = client.post(
            "/api/v1/auth/login",
            json={"username": settings.default_admin_username, "password": settings.default_admin_password},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        edge_headers = {"X-API-Key": settings.edge_api_key}
        camera_id = f"cam-{uuid.uuid4().hex[:24]}"
        area_id = f"area-{uuid.uuid4().hex[:24]}"
        track_id = f"track-{uuid.uuid4().hex[:24]}"

        response = client.post(
            "/api/v1/cameras",
            headers=headers,
            json={"id": camera_id, "name": "管理测试摄像头", "status": "online"},
        )
        assert response.status_code == 200
        response = client.patch(f"/api/v1/cameras/{camera_id}", headers=headers, json={"status": "offline"})
        assert response.status_code == 200

        response = client.post(
            "/api/v1/areas",
            headers=headers,
            json={
                "id": area_id,
                "camera_id": camera_id,
                "name": "管理测试区域",
                "polygon": [[0, 0], [100, 0], [100, 100], [0, 100]],
                "stay_threshold_seconds": 300,
                "high_risk_seconds": 600,
            },
        )
        assert response.status_code == 200
        response = client.patch(f"/api/v1/areas/{area_id}", headers=headers, json={"stay_threshold_seconds": 700})
        assert response.status_code == 422

        assert client.get("/api/v1/users", headers=headers).status_code == 200
        assert client.get("/api/v1/audit-logs", headers=headers).status_code == 200
        assert client.get("/api/v1/training-samples", headers=headers).status_code == 200

        low_event = {
            "camera_id": camera_id,
            "area_id": area_id,
            "track": {
                "id": track_id,
                "camera_id": camera_id,
                "area_id": area_id,
                "start_time": "2026-09-24T10:00:00",
                "status": "static",
                "static_seconds": 30,
            },
            "start_time": "2026-09-24T10:00:00",
            "duration_seconds": 30,
            "dedup_key": f"{track_id}:low",
        }
        response = client.post("/api/v1/edge/events", headers=edge_headers, json=low_event)
        assert response.status_code == 200
        assert response.json()["risk_level"] == "low"
        assert response.json()["task_id"] is None

        medium_track_id = f"track-{uuid.uuid4().hex[:24]}"
        medium_event = {
            "camera_id": camera_id,
            "area_id": area_id,
            "track": {
                "id": medium_track_id,
                "camera_id": camera_id,
                "area_id": area_id,
                "start_time": "2026-09-24T11:00:00",
                "static_seconds": 320,
            },
            "start_time": "2026-09-24T11:00:00",
            "duration_seconds": 320,
            "dedup_key": f"{medium_track_id}:escalation",
        }
        response = client.post("/api/v1/edge/events", headers=edge_headers, json=medium_event)
        assert response.status_code == 200
        task_id = response.json()["task_id"]
        assert task_id
        response = client.patch(
            f"/api/v1/tasks/{task_id}",
            headers=headers,
            json={"due_at": "2020-01-01T00:00:00"},
        )
        assert response.status_code == 200
        escalated = client.post("/api/v1/tasks/escalate-overdue", headers=headers)
        assert escalated.status_code == 200
        assert task_id in {item["id"] for item in escalated.json()}
        notifications = client.get("/api/v1/notifications", headers=headers)
        assert notifications.status_code == 200
        assert notifications.json()
