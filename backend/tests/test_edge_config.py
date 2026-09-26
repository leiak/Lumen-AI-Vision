"""边缘端配置热更新测试。"""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.models import Area, Camera


def _admin_token(client: TestClient) -> str:
    settings = get_settings()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": settings.default_admin_username, "password": settings.default_admin_password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_edge_config_returns_thresholds(client_with_admin):
    """GET /api/v1/edge/config 返回区域阈值 + revision。"""
    client, headers = client_with_admin
    # 先建一个 camera + area 用于测试
    with TestClient(app) as c2:
        token = _admin_token(c2)
        h = {"Authorization": f"Bearer {token}"}
        c2.post("/api/v1/cameras", json={"id": "cam-cfg", "name": "cam-cfg", "status": "online"}, headers=h)
        c2.post(
            "/api/v1/areas",
            json={
                "id": "area-cfg",
                "camera_id": "cam-cfg",
                "name": "cfg",
                "stay_threshold_seconds": 123,
                "high_risk_seconds": 456,
            },
            headers=h,
        )

    response = client.get(
        "/api/v1/edge/config",
        params={"camera_id": "cam-cfg", "area_id": "area-cfg"},
        headers={"X-API-Key": get_settings().edge_api_key},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["camera_id"] == "cam-cfg"
    assert body["area_id"] == "area-cfg"
    assert body["stay_threshold_seconds"] == 123
    assert body["high_risk_seconds"] == 456
    assert isinstance(body["revision"], int)
    assert body["revision"] > 0


def test_edge_config_unknown_camera_404(client_with_admin):
    client, _ = client_with_admin
    response = client.get(
        "/api/v1/edge/config",
        params={"camera_id": "nope"},
        headers={"X-API-Key": get_settings().edge_api_key},
    )
    assert response.status_code == 404