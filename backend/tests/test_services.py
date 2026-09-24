import shutil
from pathlib import Path
from types import SimpleNamespace

from datetime import datetime

from app.core.config import Settings
from app.services import storage
from app.services.vl_service import explain_event


def test_local_storage_upload(monkeypatch) -> None:
    root = Path("tests/tmp-storage")
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    settings = Settings(storage_backend="local", storage_local_path=str(root))
    monkeypatch.setattr(storage, "get_settings", lambda: settings)
    url = storage.upload_bytes("keyframes/test/frame.jpg", b"frame", "image/jpeg")
    assert url == "local://keyframes/test/frame.jpg"
    assert (root / "keyframes/test/frame.jpg").read_bytes() == b"frame"
    shutil.rmtree(root)


def test_vl_fallback_explanation() -> None:
    event = SimpleNamespace(duration_seconds=330, event_type="abnormal_stay")
    summary, output, score = explain_event(event, [])
    assert "6 分钟" in summary
    assert output["summary"] == summary
    assert score == 0.80


def test_task_escalation(client_with_admin):
    client, headers = client_with_admin
    response = client.post("/api/v1/tasks/escalate-overdue", headers=headers)
    assert response.status_code == 200
    assert all(item["status"] != "pending" or item["due_at"] > datetime.utcnow() for item in response.json())
