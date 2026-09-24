from datetime import timedelta
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


def read_bytes(storage_url: str) -> tuple[bytes, str]:
    settings = get_settings()
    if storage_url.startswith("local://"):
        root = Path(settings.storage_local_path).resolve()
        relative = storage_url.removeprefix("local://")
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise FileNotFoundError(storage_url)
        return path.read_bytes(), "image/jpeg"

    if storage_url.startswith("minio://"):
        bucket, object_key = storage_url.removeprefix("minio://").split("/", 1)
        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=False,
        )
        response = client.get_object(bucket, object_key)
        try:
            return response.read(), "image/jpeg"
        finally:
            response.close()
            response.release_conn()

    raise ValueError(f"unsupported storage url: {storage_url}")


def presigned_url(storage_url: str, expires_seconds: int = 3600) -> str:
    settings = get_settings()
    if not storage_url.startswith("minio://"):
        return storage_url
    bucket, object_key = storage_url.removeprefix("minio://").split("/", 1)
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )
    return client.presigned_get_object(bucket, object_key, expires=timedelta(seconds=expires_seconds))


def io_bytes(data: bytes):
    import io
    return io.BytesIO(data)


def object_name(prefix: str, extension: str = "jpg") -> str:
    return f"{prefix}/{uuid4().hex}.{extension}"
