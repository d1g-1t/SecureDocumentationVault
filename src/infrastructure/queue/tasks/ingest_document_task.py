from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select

from src.infrastructure.crypto.checksum_service import ChecksumService
from src.infrastructure.crypto.envelope_encryption import EnvelopeEncryptionService
from src.infrastructure.database.models import DocumentVersionModel, StorageObjectModel
from src.infrastructure.database.session import AsyncSessionFactory
from src.infrastructure.observability.metrics import documents_uploaded_total
from src.infrastructure.queue.celery_app import celery_app
from src.infrastructure.queue.tasks._async_bridge import run_sync
from src.infrastructure.storage.minio_storage import MinioStorage

log = structlog.get_logger(__name__)


@celery_app.task(
    name="vault.ingest.ingest_document",
    queue="vault.ingest",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=5,
    acks_late=True,
)
def ingest_document_task(
    self: object,
    version_id: str,
    tenant_id: str,
    document_type: str = "unknown",
) -> dict[str, object]:
    return run_sync(_ingest_async(version_id, tenant_id, document_type))


async def _ingest_async(
    version_id: str,
    tenant_id: str,
    document_type: str,
) -> dict[str, object]:
    log.info("ingest.start", version_id=version_id, tenant_id=tenant_id)

    sf = AsyncSessionFactory()
    storage = MinioStorage()
    encryption = EnvelopeEncryptionService()
    checksum_svc = ChecksumService()

    async with sf.session() as session:
        version = await session.scalar(
            select(DocumentVersionModel).where(
                DocumentVersionModel.id == UUID(version_id)
            )
        )
        if version is None:
            log.warning("ingest.version_missing", version_id=version_id)
            return {"status": "missing", "version_id": version_id}

        storage_obj = (
            await session.scalar(
                select(StorageObjectModel).where(
                    StorageObjectModel.id == version.storage_object_id
                )
            )
            if version.storage_object_id
            else None
        )

    if storage_obj is None:
        log.error("ingest.storage_object_missing", version_id=version_id)
        return {"status": "no_storage_object", "version_id": version_id}

    encrypted_bytes = storage.get_object(storage_obj.object_key)
    actual_checksum = checksum_svc.compute(encrypted_bytes)
    integrity_ok = actual_checksum == storage_obj.object_checksum

    try:
        dek = encryption.unwrap_dek(version.encryption_key_id)
        encryption.decrypt_bytes(encrypted_bytes, dek)
        decrypt_ok = True
    except Exception as exc:
        log.error("ingest.decrypt_failed", version_id=version_id, error=str(exc))
        decrypt_ok = False

    documents_uploaded_total.labels(
        tenant_id=tenant_id, document_type=document_type
    ).inc()

    log.info(
        "ingest.done",
        version_id=version_id,
        integrity_ok=integrity_ok,
        decrypt_ok=decrypt_ok,
    )
    return {
        "version_id": version_id,
        "integrity_ok": integrity_ok,
        "decrypt_ok": decrypt_ok,
    }
