import argparse
from datetime import datetime, timedelta

import cv2
import httpx
import numpy as np


EVENTS = [
    {
        "suffix": "001",
        "duration_seconds": 320,
        "risk": "medium",
        "review": True,
    },
    {
        "suffix": "002",
        "duration_seconds": 700,
        "risk": "high",
        "review": False,
    },
    {
        "suffix": "003",
        "duration_seconds": 60,
        "risk": "low",
        "review": False,
    },
]


def login(client: httpx.Client, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def ensure_camera_area(client: httpx.Client, headers: dict[str, str], camera_id: str, area_id: str) -> None:
    cameras = client.get("/api/v1/cameras", headers=headers).raise_for_status().json()
    if camera_id not in {item["id"] for item in cameras}:
        client.post(
            "/api/v1/cameras",
            headers=headers,
            json={"id": camera_id, "name": "Demo 库门口", "location": "local-demo", "status": "online"},
        ).raise_for_status()

    areas = client.get("/api/v1/areas", headers=headers).raise_for_status().json()
    if area_id not in {item["id"] for item in areas}:
        client.post(
            "/api/v1/areas",
            headers=headers,
            json={
                "id": area_id,
                "camera_id": camera_id,
                "name": "Demo 停留区域",
                "area_type": "gate",
                "polygon": [[120, 130], [1120, 130], [1120, 620], [120, 620]],
                "stay_threshold_seconds": 300,
                "high_risk_seconds": 600,
                "enabled": True,
            },
        ).raise_for_status()


def demo_frame(title: str, seconds: int) -> bytes:
    image = np.full((360, 640, 3), 245, dtype=np.uint8)
    cv2.rectangle(image, (80, 220), (240, 300), (60, 60, 200), -1)
    cv2.rectangle(image, (100, 180), (220, 220), (40, 40, 160), -1)
    cv2.rectangle(image, (120, 130), [200, 180], (240, 240, 240), -1)
    cv2.polylines(image, [np.array([[40, 330], [600, 330], [620, 350], [20, 350]])], True, (180, 180, 180), 2)
    cv2.putText(image, "DEMO KEYFRAME", (24, 46), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (30, 30, 30), 2)
    cv2.putText(image, title, (24, 86), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (70, 70, 70), 2)
    cv2.putText(image, f"static_seconds={seconds}", (24, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (70, 70, 70), 2)
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if not ok:
        raise RuntimeError("failed to encode demo frame")
    return encoded.tobytes()


def seed_event(client: httpx.Client, headers: dict[str, str], edge_headers: dict[str, str], camera_id: str, area_id: str, item: dict) -> str:
    suffix = item["suffix"]
    track_id = f"track-demo-{suffix}"
    event_id = f"evt-demo-{suffix}"
    start_time = datetime.utcnow() - timedelta(minutes=int(item["suffix"]) * 17)
    duration = item["duration_seconds"]
    dedup_key = f"{track_id}:abnormal_stay:demo"

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
                "vehicle_type": "truck",
                "start_time": start_time.isoformat(),
                "status": "static",
                "static_seconds": duration,
            },
            "event_type_hint": "abnormal_stay",
            "start_time": start_time.isoformat(),
            "duration_seconds": duration,
            "dedup_key": dedup_key,
        },
    )
    response.raise_for_status()
    created_event_id = response.json()["event_id"]

    for frame_index in range(2):
        seconds = duration if frame_index == 0 else max(1, duration // 2)
        timestamp = start_time + timedelta(seconds=seconds)
        frame_id = f"frame-demo-{suffix}-{frame_index}"
        upload = client.post(
            "/api/v1/edge/keyframes/upload",
            headers=edge_headers,
            data={
                "track_id": track_id,
                "event_id": created_event_id,
                "frame_id": frame_id,
                "frame_role": "static_start" if frame_index == 0 else "state_change",
                "timestamp": timestamp.isoformat(),
            },
            files={"file": ("demo.jpg", demo_frame(f"DEMO EVENT {suffix}", seconds), "image/jpeg")},
        )
        upload.raise_for_status()

    client.post(
        "/api/v1/models/temporal/classify",
        headers=headers,
        json={"event_id": created_event_id},
    ).raise_for_status()
    client.post(
        "/api/v1/models/vl/explain",
        headers=headers,
        json={"event_id": created_event_id},
    ).raise_for_status()

    if item["review"]:
        review = client.post(
            f"/api/v1/events/{created_event_id}/review",
            headers=headers,
            json={
                "reviewer_id": "00000000-0000-0000-0000-000000000001",
                "result": "abnormal",
                "corrected_event_type": "abnormal_stay",
                "comment": "Demo seeded abnormal stay",
            },
        )
        review.raise_for_status()

    return created_event_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed visible demo events, keyframes, tasks and notifications.")
    parser.add_argument("--base-url", default="http://localhost:5032")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--camera-id", default="cam-gate-demo-001")
    parser.add_argument("--area-id", default="area-gate-demo-001")
    parser.add_argument("--edge-api-key", default="change-this-edge-key")
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url.rstrip("/"), timeout=20)
    headers = login(client, args.username, args.password)
    edge_headers = {"X-API-Key": args.edge_api_key}
    ensure_camera_area(client, headers, args.camera_id, args.area_id)
    for item in EVENTS:
        event_id = seed_event(client, headers, edge_headers, args.camera_id, args.area_id, item)
        print(f"seeded={event_id}")

    print("demo_data_ready=1")


if __name__ == "__main__":
    main()
