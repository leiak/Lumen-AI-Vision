import uuid
from datetime import datetime

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_operations_metrics_returns_business_kpis() -> None:
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
        now = datetime.utcnow().replace(microsecond=0).isoformat()

        assert client.post(
            "/api/v1/cameras",
            headers=headers,
            json={"id": camera_id, "name": "运营测试摄像头"},
        ).status_code == 200
        assert client.post(
            "/api/v1/areas",
            headers=headers,
            json={
                "id": area_id,
                "camera_id": camera_id,
                "name": "运营测试区域",
                "stay_threshold_seconds": 300,
                "high_risk_seconds": 600,
            },
        ).status_code == 200

        response = client.post(
            "/api/v1/edge/events",
            headers=edge_headers,
            json={
                "camera_id": camera_id,
                "area_id": area_id,
                "track": {
                    "id": track_id,
                    "camera_id": camera_id,
                    "area_id": area_id,
                    "start_time": now,
                    "status": "static",
                    "static_seconds": 320,
                },
                "start_time": now,
                "duration_seconds": 320,
                "behaviors": [
                    {
                        "person_track_id": f"track-{camera_id}-person-1",
                        "vehicle_track_id": track_id,
                        "behavior_label": "person_present",
                        "behavior_confidence": 0.68,
                        "near_vehicle_seconds": 320,
                        "sequence_frame_count": 12,
                        "sequence_start_time": now,
                        "sequence_end_time": now,
                    }
                ],
            },
        )
        assert response.status_code == 200
        event_id = response.json()["event_id"]

        review = client.post(
            f"/api/v1/events/{event_id}/review",
            headers=headers,
            json={"reviewer_id": "reviewer", "result": "abnormal"},
        )
        assert review.status_code == 200

        operations = client.get("/api/v1/metrics/operations", headers=headers, params={"days": 7})
        assert operations.status_code == 200
        payload = operations.json()
        assert payload["window"]["days"] == 7
        assert payload["events"]["total"] >= 1
        assert payload["events"]["by_risk"]["medium"] >= 1
        assert payload["tasks"]["total"] >= 1
        assert payload["notifications"]["total"] >= 1
        assert payload["reviews"]["total"] >= 1
        assert payload["behaviors"]["by_label"]["person_present"] >= 1
        assert payload["hotspots"]["areas"]
        assert payload["daily_trend"]
