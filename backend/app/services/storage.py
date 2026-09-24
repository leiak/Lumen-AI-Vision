from pathlib import Path
from uuid import uuid4

from minio import Minio

from app.core.config import get_settings


def upload_bytes(object_name: str, data: bytes, content_type: str | None = None) -> str:
    settings = get_settings()
    content_type = content_type or settings.keyframe_content_type
    if settings.storage_backend == "local":
        path = Path(settings.storage_local_path) / object_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"local://{object_name}"

    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)
    client.put_object(
        settings.minio_bucket,
        object_name,
        data=io_bytes(data),
        length=len(data),
        content_type=content_type,
    )
    return f"minio://{settings.minio_bucket}/{object_name}"


def io_bytes(data: bytes):
    import io
    return io.BytesIO(data)


def object_name(prefix: str, extension: str = "jpg") -> str:
    return f"{prefix}/{uuid4().hex}.{extension}"
