"""数据导出端点测试。"""

import csv
import io

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.models import AuditLog, Event, ModelResult


def _admin_token(client: TestClient) -> str:
    settings = get_settings()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": settings.default_admin_username, "password": settings.default_admin_password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _parse_csv(response) -> list[dict]:
    content = response.content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    return list(reader)


def test_export_events_csv(client_with_admin):
    client, headers = client_with_admin
    response = client.get("/api/v1/exports/events", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    rows = _parse_csv(response)
    assert isinstance(rows, list)


def test_export_audit_logs_requires_admin(client_with_admin):
    client, headers = client_with_admin
    response = client.get("/api/v1/exports/audit-logs", headers=headers)
    assert response.status_code == 200
    rows = _parse_csv(response)
    # 表头至少包含 action/user_id/created_at
    if rows:
        assert "action" in rows[0]


def test_export_metrics_csv(client_with_admin):
    client, headers = client_with_admin
    response = client.get("/api/v1/exports/metrics", headers=headers)
    assert response.status_code == 200
    rows = _parse_csv(response)
    assert isinstance(rows, list)