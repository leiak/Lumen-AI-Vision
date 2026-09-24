import json

import httpx

from app.core.config import get_settings
from app.models import Event, Keyframe
from app.services.storage import presigned_url


def explain_event(event: Event, keyframes: list[Keyframe]) -> tuple[str, dict, float]:
    settings = get_settings()
    if not settings.vl_api_url:
        return _fallback(event)

    content: list[dict] = [
        {
            "type": "text",
            "text": (
                "你是仓库安防分析助手。请基于关键帧判断车辆停留行为，"
                "输出中文 JSON：summary、behavior、possible_reason。"
                "禁止编造车牌、人物身份或责任结论。"
            ),
        }
    ]
    for frame in keyframes:
        try:
            image_url = presigned_url(frame.storage_url)
        except Exception:
            image_url = frame.storage_url
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": image_url},
            }
        )
    response = httpx.post(
        settings.vl_api_url.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {settings.vl_api_key}"},
        json={
            "model": settings.vl_model_name,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.1,
        },
        timeout=settings.vl_api_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    text = payload["choices"][0]["message"]["content"]
    try:
        parsed = json.loads(text)
        summary = parsed.get("summary", text)
        behavior = parsed.get("behavior", [])
        possible_reason = parsed.get("possible_reason", "")
    except json.JSONDecodeError:
        summary = text
        behavior = []
        possible_reason = ""
    score = float(payload.get("usage", {}).get("confidence", 0.78))
    return summary, {"summary": summary, "behavior": behavior, "possible_reason": possible_reason}, score


def _fallback(event: Event) -> tuple[str, dict, float]:
    minutes = max(1, round(event.duration_seconds / 60))
    summary = f"车辆在关联区域停留约 {minutes} 分钟，系统判定为 {event.event_type}，建议人工确认现场状态。"
    return summary, {
        "summary": summary,
        "behavior": ["车辆进入区域", "车辆停止", "车辆持续停留"],
        "possible_reason": "可能为异常滞留或等待作业，需要人工确认。",
    }, 0.80
