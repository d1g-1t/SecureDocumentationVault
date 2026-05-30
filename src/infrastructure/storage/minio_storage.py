from __future__ import annotations

import io
import uuid
from datetime import timedelta

from minio import Minio
from minio.error import S3Error
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class MinioStorage:

    def __init__(self, settings: object = None) -> None:
        cfg = get_settings()
        self._client = Minio(
            cfg.minio_endpoint,
            access_key=cfg.minio_root_user,
            secret_key=cfg.minio_root_password,
            secure=cfg.minio_secure,
        )
        self._bucket = cfg.minio_bucket_documents
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
                logger.info("minio_bucket_created", bucket=self._bucket)
        except S3Error as exc:
            logger.error("minio_bucket_ensure_failed", error=str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.warning("minio_bucket_ensure_skipped", error=str(exc))

    @staticmethod
    def build_object_key(
        tenant_id: uuid.UUID,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
        file_name: str,
    ) -> str:
        return f"{tenant_id}/{document_id}/{version_id}/{file_name}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
    )
    def put_object(
        self,
        object_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        self._client.put_object(
            bucket_name=self._bucket,
            object_name=object_key,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
            metadata={"encrypted": "true"},
        )
        logger.info("minio_object_uploaded", key=object_key, size=len(data))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
    )
    def get_object(self, object_key: str) -> bytes:
        try:
            response = self._client.get_object(self._bucket, object_key)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as exc:
            logger.error("minio_get_failed", key=object_key, error=str(exc))
            raise FileNotFoundError(f"Object {object_key} not found in MinIO") from exc

    def delete_object(self, object_key: str) -> None:
        self._client.remove_object(self._bucket, object_key)
        logger.info("minio_object_deleted", key=object_key)

    def object_exists(self, object_key: str) -> bool:
        try:
            self._client.stat_object(self._bucket, object_key)
            return True
        except S3Error:
            return False

    def presigned_get_url(self, object_key: str, expires: timedelta = timedelta(minutes=15)) -> str:
        return self._client.presigned_get_object(
            self._bucket, object_key, expires=expires
        )
