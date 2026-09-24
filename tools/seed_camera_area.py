import argparse

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a test camera and detection area.")
    parser.add_argument("--base-url", default="http://localhost:5032")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--camera-id", default="cam-gate-test-001")
    parser.add_argument("--area-id", default="area-gate-test-001")
    parser.add_argument("--stay-threshold-seconds", type=int, default=30)
    parser.add_argument("--high-risk-seconds", type=int, default=60)
    parser.add_argument("--polygon", default="[[0.15,0.20],[0.85,0.20],[0.85,0.85],[0.15,0.85]]")
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url.rstrip("/"), timeout=10)
    login = client.post(
        "/api/v1/auth/login",
        json={"username": args.username, "password": args.password},
    )
    login.raise_for_status()
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    cameras = client.get("/api/v1/cameras", headers=headers).raise_for_status().json()
    if args.camera_id not in {item["id"] for item in cameras}:
        client.post(
            "/api/v1/cameras",
            headers=headers,
            json={
                "id": args.camera_id,
                "name": "离线测试库门口",
                "location": "local-video-test",
                "status": "online",
            },
        ).raise_for_status()

    areas = client.get("/api/v1/areas", headers=headers).raise_for_status().json()
    if args.area_id not in {item["id"] for item in areas}:
        client.post(
            "/api/v1/areas",
            headers=headers,
            json={
                "id": args.area_id,
                "camera_id": args.camera_id,
                "name": "离线测试区域",
                "area_type": "gate",
                "polygon": json_polygon(args.polygon),
                "stay_threshold_seconds": args.stay_threshold_seconds,
                "high_risk_seconds": args.high_risk_seconds,
                "enabled": True,
            },
        ).raise_for_status()

    print(f"camera_id={args.camera_id}")
    print(f"area_id={args.area_id}")


def json_polygon(value: str) -> list[list[int]]:
    import json

    return json.loads(value)


if __name__ == "__main__":
    main()
