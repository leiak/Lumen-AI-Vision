import smtplib
from email.message import EmailMessage

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Notification


def dispatch_notification(db: Session, notification: Notification, message: str) -> Notification:
    settings = get_settings()
    try:
        if notification.channel == "webhook":
            if not settings.notification_webhook_url:
                raise ValueError("webhook url not configured")
            response = httpx.post(
                settings.notification_webhook_url,
                json={"event_id": notification.event_id, "task_id": notification.task_id, "text": message},
                timeout=10,
            )
            response.raise_for_status()
        elif notification.channel == "email":
            _send_email(notification.receiver_id, message)
        notification.status = "sent"
        notification.retry_count += 1
    except Exception:
        notification.status = "failed"
        notification.retry_count += 1
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
