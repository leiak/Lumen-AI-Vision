from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings


settings = get_settings()
celery_app = Celery(
    "visual_recognition",
    broker=settings.rabbitmq_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    beat_schedule={
        "escalate-overdue-every-minute": {
            "task": "tasks.escalate_overdue",
            "schedule": 60.0,
        },
        "cleanup-old-data-daily": {
            "task": "tasks.cleanup_old_data",
            # 每天 03:xx（避开业务高峰）；用 cron 表达式由 hour 决定分钟数避免整点
            "schedule": crontab(minute=17, hour=settings.retention_cleanup_hour),
        },
    },
)
