import uuid
from io import BytesIO

import structlog
from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = structlog.get_logger()


class StorageService:
    def __init__(self):
        self.client = Minio(
            f"{settings.minio_host}:{settings.minio_port}",
            access_key=settings.minio_root_user,
            secret_key=settings.minio_root_password,
            secure=False,
        )
        self.bucket = settings.minio_bucket

    def ensure_bucket(self):
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
            logger.info("storage.bucket_created", bucket=self.bucket)

    def generate_key(self, user_id: int, filename: str) -> str:
        ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
        unique = uuid.uuid4().hex
        return f"users/{user_id}/{unique}.{ext}" if ext else f"users/{user_id}/{unique}"

    def upload(self, key: str, data: bytes, content_type: str) -> int:
        size = len(data)
        self.client.put_object(
            self.bucket,
            key,
            BytesIO(data),
            length=size,
            content_type=content_type,
        )
        logger.info("storage.upload", key=key, size_bytes=size)
        return size

    def get_download_url(self, key: str, expires_seconds: int = 3600) -> str:
        from datetime import timedelta
        return self.client.presigned_get_object(
            self.bucket,
            key,
            expires=timedelta(seconds=expires_seconds),
        )

    def delete(self, key: str):
        try:
            self.client.remove_object(self.bucket, key)
            logger.info("storage.delete", key=key)
        except S3Error as e:
            logger.error("storage.delete_failed", key=key, error=str(e))
            raise


storage_service = StorageService()
