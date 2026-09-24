import uuid

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
