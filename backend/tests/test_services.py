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


def test_vl_filters_unprocessed_keyframes(monkeypatch) -> None:
    """VL 服务只接受 privacy_processed=True 的关键帧；否则回退到本地解释。"""
    from app.core.config import Settings
    from app.services import vl_service
    settings = Settings(vl_api_url="http://vl.test")
    monkeypatch.setattr(vl_service, "get_settings", lambda: settings)

    event = SimpleNamespace(duration_seconds=120, event_type="abnormal_stay")
    unsafe = SimpleNamespace(privacy_processed=False, storage_url="local://x")
    safe = SimpleNamespace(privacy_processed=True, storage_url="local://y")

    # 没有脱敏帧时必须回退
    summary, output, score = explain_event(event, [unsafe])
    assert output["fallback_reason"] == "no privacy-processed keyframes available"
    assert score == 0.80

    # 全部未脱敏也必须回退
    summary, output, score = explain_event(event, [unsafe, unsafe])
    assert output["fallback_reason"] == "no privacy-processed keyframes available"


def test_task_escalation(client_with_admin):
    client, headers = client_with_admin
    response = client.post("/api/v1/tasks/escalate-overdue", headers=headers)
    assert response.status_code == 200
    assert all(item["status"] != "pending" or item["due_at"] > datetime.utcnow() for item in response.json())
