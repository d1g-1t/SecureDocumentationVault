from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select

from src.domain.entities.audit_event import AuditEvent
from src.domain.entities.signature_record import SignatureRecord
from src.domain.value_objects import EventType, SignatureStatus, SignatureType
from src.infrastructure.crypto.envelope_encryption import EnvelopeEncryptionService
from src.infrastructure.crypto.integrity_chain import IntegrityChainService
from src.infrastructure.database.models import (
    DocumentVersionModel,
    StorageObjectModel,
)
from src.infrastructure.database.repositories.audit_repository import AuditRepository
from src.infrastructure.database.repositories.signature_repository import (
    SignatureRepository,
)
from src.infrastructure.database.session import AsyncSessionFactory
from src.infrastructure.observability.metrics import (
    signature_verification_duration,
    signature_verifications_total,
)
from src.infrastructure.queue.celery_app import celery_app
from src.infrastructure.queue.tasks._async_bridge import run_sync
from src.infrastructure.signatures.cms_verifier import CmsVerifier
from src.infrastructure.storage.minio_storage import MinioStorage

log = structlog.get_logger(__name__)


@celery_app.task(
    name="vault.ingest.verify_signature",
    queue="vault.ingest",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    acks_late=True,
)
def verify_signature_task(
    self: object,
    version_id: str,
    tenant_id: str,
    signature_type: str = "CMS",
    detached_signature_b64: str | None = None,
) -> dict[str, object]:
    return run_sync(
        _verify_async(version_id, tenant_id, signature_type, detached_signature_b64)
    )


async def _verify_async(
    version_id: str,
    tenant_id: str,
    signature_type: str,
    detached_signature_b64: str | None,
) -> dict[str, object]:
    log.info("signature.verify.start", version_id=version_id)

    sf = AsyncSessionFactory()
    storage = MinioStorage()
    encryption = EnvelopeEncryptionService()
    verifier = CmsVerifier()
    chain = IntegrityChainService()

    async with sf.session() as session:
        version = await session.scalar(
            select(DocumentVersionModel).where(
                DocumentVersionModel.id == UUID(version_id)
            )
        )
        if version is None or version.storage_object_id is None:
            raise ValueError(f"Version {version_id} not found or has no storage object")

        storage_obj = await session.scalar(
            select(StorageObjectModel).where(
                StorageObjectModel.id == version.storage_object_id
            )
        )
        if storage_obj is None:
            raise ValueError(f"Storage object missing for version {version_id}")

    encrypted = storage.get_object(storage_obj.object_key)
    dek = encryption.unwrap_dek(version.encryption_key_id)
    plain = encryption.decrypt_bytes(encrypted, dek)

    sig_b64 = detached_signature_b64 or ""

    with signature_verification_duration.labels(signature_type=signature_type).time():
        report = verifier.verify(
            document_bytes=plain,
            signature_b64=sig_b64,
            signature_type=SignatureType(signature_type),
        )

    sig_repo = SignatureRepository(sf)
    audit_repo = AuditRepository(sf, chain)

    record = SignatureRecord(
        id=uuid4(),
        document_version_id=UUID(version_id),
        signature_type=SignatureType(signature_type),
        verification_status=SignatureStatus(report.get("status", "UNKNOWN")),
        signer_name=report.get("signer_name"),
        signer_inn=report.get("signer_inn"),
        certificate_subject=report.get("certificate_subject"),
        certificate_issuer=report.get("certificate_issuer"),
        certificate_serial=report.get("certificate_serial"),
        signing_time=report.get("signing_time"),
        signature_hash=report.get("signature_hash"),
        raw_report=report,
        verified_at=datetime.now(UTC),
    )
    saved = await sig_repo.create(record)

    last_hash = await audit_repo.get_last_hash("document_version", UUID(version_id))
    payload = {
        "signature_id": str(saved.id),
        "verification_status": saved.verification_status.value,
        "signature_type": signature_type,
    }
    event_hash = chain.compute_hash(payload, last_hash)
    await audit_repo.create_event(
        AuditEvent(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            actor_user_id=None,
            resource_type="document_version",
            resource_id=UUID(version_id),
            event_type=EventType.SIGNATURE_VERIFIED,
            ip_address=None,
            user_agent="celery:verify_signature",
            trace_id=None,
            payload=payload,
            prev_event_hash=last_hash,
            event_hash=event_hash,
            created_at=datetime.now(UTC),
        )
    )

    signature_verifications_total.labels(
        tenant_id=tenant_id,
        signature_type=signature_type,
        status=saved.verification_status.value,
    ).inc()

    log.info(
        "signature.verify.done",
        version_id=version_id,
        status=saved.verification_status.value,
    )
    return {
        "signature_id": str(saved.id),
        "status": saved.verification_status.value,
    }
