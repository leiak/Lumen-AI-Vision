import argparse
import sys

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate that an edge video test created a complete event.")
    parser.add_argument("--base-url", default="http://localhost:5032")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--camera-id", default="cam-gate-test-001")
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url.rstrip("/"), timeout=15)
    login = client.post(
        "/api/v1/auth/login",
        json={"username": args.username, "password": args.password},
    )
    login.raise_for_status()
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    events = client.get("/api/v1/events", params={"camera_id": args.camera_id}, headers=headers)
    events.raise_for_status()
    records = events.json()
    if not records:
        print("未找到事件：请确认边缘进程超过停留阈值后才结束")
        sys.exit(1)

    event = records[0]
    event_id = event["id"]
    keyframes = client.get(f"/api/v1/events/{event_id}/keyframes", headers=headers)
    keyframes.raise_for_status()
    frames = keyframes.json()

    failures: list[str] = []
    if event["duration_seconds"] <= 0:
        failures.append("停留时长无效")
    if event["risk_level"] not in {"medium", "high", "critical"}:
        failures.append("风险等级未达到处理条件")
    if not frames:
        failures.append("关键帧缺失")

    if frames:
        frame_id = frames[0]["id"]
        file_response = client.get(f"/api/v1/keyframes/{frame_id}/file", headers=headers)
        if file_response.status_code != 200:
            failures.append(f"关键帧文件访问失败：HTTP {file_response.status_code}")

    print(f"event_id={event_id}")
    print(f"duration_seconds={event['duration_seconds']}")
    print(f"risk_level={event['risk_level']}")
    print(f"keyframes={len(frames)}")
    if failures:
        print("；".join(failures))
        sys.exit(1)
    print("事件闭环验证通过")


if __name__ == "__main__":
    main()
