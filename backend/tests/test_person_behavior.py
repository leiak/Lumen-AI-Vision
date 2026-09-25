import uuid
from datetime import datetime

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_edge_event_uses_person_behavior_to_escalate_risk() -> None:
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
        person_track_id = f"track-{camera_id}-person-1"

        assert client.post(
            "/api/v1/cameras",
            headers=headers,
            json={"id": camera_id, "name": "行为测试摄像头"},
        ).status_code == 200
        assert client.post(
            "/api/v1/areas",
            headers=headers,
            json={
                "id": area_id,
                "camera_id": camera_id,
                "name": "行为测试区域",
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
                    "start_time": "2026-09-24T10:00:00",
                    "status": "static",
                    "static_seconds": 60,
                },
                "start_time": "2026-09-24T10:00:00",
                "duration_seconds": 60,
                "behaviors": [
                    {
                        "person_track_id": person_track_id,
                        "vehicle_track_id": track_id,
                        "behavior_label": "fall_down",
                        "behavior_confidence": 0.9,
                        "near_vehicle_seconds": 60,
                        "sequence_frame_count": 12,
                        "sequence_start_time": "2026-09-24T10:00:00",
                        "sequence_end_time": "2026-09-24T10:01:00",
                        "model_type": "rule",
                        "model_version": "person-behavior-rule-v1",
                    }
                ],
            },
        )
        assert response.status_code == 200
        assert response.json()["risk_level"] == "critical"
        event_id = response.json()["event_id"]

        detail = client.get(f"/api/v1/events/{event_id}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["risk_level"] == "critical"
        assert len(detail.json()["behavior_results"]) == 1
        assert detail.json()["behavior_results"][0]["person_track_id"] == person_track_id
        assert detail.json()["behavior_results"][0]["behavior_label"] == "fall_down"
