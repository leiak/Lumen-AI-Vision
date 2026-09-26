"""通知分发服务。

支持的渠道（运维设计 §3.1）：
  - in_app   : 站内通知，写入数据库即视为已发送
  - webhook  : 向 settings.notification_webhook_url 推送
  - email    : 经 SMTP 发送（需配置 SMTP_* 环境变量）
  - im/sms/phone_call  : 当前为 noop 占位，预留扩展
未识别的渠道会标记为 failed。
"""

import smtplib
from datetime import datetime
from email.message import EmailMessage

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Notification


def dispatch_notification(db: Session, notification: Notification, message: str) -> Notification:
    settings = get_settings()
    try:
        if notification.channel == "in_app":
            # 站内通知：写入即视为已送达，前端通过 GET /api/v1/notifications 拉取
            notification.sent_at = datetime.utcnow()
            notification.status = "sent"
        elif notification.channel == "webhook":
            if not settings.notification_webhook_url:
                raise ValueError("webhook url not configured")
            response = httpx.post(
                settings.notification_webhook_url,
                json={"event_id": notification.event_id, "task_id": notification.task_id, "text": message},
                timeout=10,
            )
            response.raise_for_status()
            notification.sent_at = datetime.utcnow()
            notification.status = "sent"
        elif notification.channel == "email":
            _send_email(notification.receiver_id, message)
            notification.sent_at = datetime.utcnow()
            notification.status = "sent"
        elif notification.channel in {"im", "sms", "phone_call"}:
            # 暂未实现，仅记录预留扩展点
            raise NotImplementedError(f"channel {notification.channel} not yet wired")
        else:
            raise ValueError(f"unsupported channel {notification.channel}")
        notification.retry_count = (notification.retry_count or 0) + 1
    except Exception:
        notification.status = "failed"
        notification.retry_count = (notification.retry_count or 0) + 1
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def _send_email(receiver: str, message: str) -> None:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_sender:
        raise ValueError("smtp not configured")
    email = EmailMessage()
    email["From"] = settings.smtp_sender
    email["To"] = receiver
    email["Subject"] = "异常停留告警"
    email.set_content(message)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(email)