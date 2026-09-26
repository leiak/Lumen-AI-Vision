from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Visual Recognition API"
    environment: str = "development"
    database_url: str = "sqlite:///./visual_recognition.db"
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "keyframes"
    storage_backend: str = "minio"
    storage_local_path: str = "./storage"
    keyframe_content_type: str = "image/jpeg"
    vl_api_timeout_seconds: int = 20
    vl_model_version: str = "v0.1.0"
    notification_webhook_url: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_sender: str | None = None
    smtp_use_tls: bool = True
    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 720
    default_admin_username: str = "admin"
    default_admin_password: str = "admin123"
    default_admin_role: str = "admin"
    edge_api_key: str = "edge-dev-key"
    vl_api_url: str | None = None
    vl_api_key: str | None = None
    vl_model_name: str = "qwen2.5-vl"
    temporal_model_name: str = "keyframe-temporal-transformer"
    temporal_model_version: str = "v0.1.0"

    # 数据保留（运维设计 §3.4）：超过期限的行由 Celery beat 清理任务删除
    retention_event_days: int = 90  # 事件主表
    retention_audit_days: int = 365  # 审计日志
    retention_metrics_days: int = 730  # 模型推理结果 / 时序分类
    retention_notification_days: int = 365  # 通知记录
    retention_cleanup_hour: int = 3  # 每天 03:xx 触发（避开业务高峰）

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
