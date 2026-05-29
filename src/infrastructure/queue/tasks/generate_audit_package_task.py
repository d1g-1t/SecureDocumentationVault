from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select

from src.core.config import get_settings
from src.domain.entities.audit_event import AuditEvent
from src.domain.value_objects import EventType, StorageClass
from src.infrastructure.crypto.integrity_chain import IntegrityChainService
from src.infrastructure.database.models import (
    AuditEventModel,
    DocumentModel,
    DocumentVersionModel,
    SignatureRecordModel,
)
from src.infrastructure.database.repositories.audit_repository import AuditRepository
from src.infrastructure.database.repositories.document_repository import (
    DocumentRepository,
)
from src.infrastructure.database.session import AsyncSessionFactory
from src.infrastructure.observability.metrics import (
    audit_package_generation_duration,
)
from src.infrastructure.queue.celery_app import celery_app
from src.infrastructure.queue.tasks._async_bridge import run_sync
from src.infrastructure.storage.minio_storage import MinioStorage

log = structlog.get_logger(__name__)


@celery_app.task(
    name="vault.audit.generate_audit_package",
    queue="vault.audit",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    acks_late=True,
)
def generate_audit_package_task(
    self: object,
    document_id: str,
    tenant_id: str,
    requested_by: str,
) -> dict[str, str]:
    return run_sync(_build_package(document_id, tenant_id, requested_by))


async def _build_package(
    document_id: str,
    tenant_id: str,
    requested_by: str,
) -> dict[str, str]:
    log.info("audit_package.start", document_id=document_id)

    sf = AsyncSessionFactory()
    storage = MinioStorage()
    chain = IntegrityChainService()
    cfg = get_settings()

    with audit_package_generation_duration.time():
        async with sf.session() as session:
            doc = await session.scalar(
                select(DocumentModel).where(DocumentModel.id == UUID(document_id))
            )
            if doc is None:
                raise ValueError(f"Document {document_id} not found")

            versions = (
                await session.scalars(
                    select(DocumentVersionModel).where(
                        DocumentVersionModel.document_id == UUID(document_id)
                    )
                )
            ).all()
            version_ids = [v.id for v in versions]

            events = (
                await session.scalars(
                    select(AuditEventModel)
                    .where(
                        AuditEventModel.resource_type == "document",
                        AuditEventModel.resource_id == UUID(document_id),
                    )
                    .order_by(AuditEventModel.created_at.asc())
                )
            ).all()

            sigs = (
                await session.scalars(
                    select(SignatureRecordModel).where(
                        SignatureRecordModel.document_version_id.in_(version_ids)
                    )
                )
                if version_ids
                else None
            )
            sig_rows = list(sigs.all()) if sigs is not None else []

        event_dicts = [
            {
                "payload": e.payload,
                "prev_event_hash": e.prev_event_hash,
                "event_hash": e.event_hash,
            }
            for e in events
        ]
        chain_valid, first_broken = chain.verify_chain(event_dicts)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "metadata.json",
                json.dumps(
                    {
                        "document_id": document_id,
                        "tenant_id": tenant_id,
                        "title": doc.title,
                        "document_type": doc.document_type,
                        "status": doc.status,
                        "created_at": doc.created_at.isoformat(),
                        "versions": [
                            {
                                "id": str(v.id),
                                "version_number": v.version_number,
                                "file_name": v.file_name,
                                "sha256": v.sha256_checksum,
                            }
                            for v in versions
                        ],
                        "package_generated_at": datetime.now(UTC).isoformat(),
                        "generated_by": requested_by,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            audit_trail = "\n".join(
                json.dumps(
                    {
                        "id": str(e.id),
                        "event_type": e.event_type,
                        "actor_user_id": str(e.actor_user_id) if e.actor_user_id else None,
                        "created_at": e.created_at.isoformat(),
                        "payload": e.payload,
                        "prev_event_hash": e.prev_event_hash,
                        "event_hash": e.event_hash,
                    },
                    ensure_ascii=False,
                )
                for e in events
            )
            zf.writestr("audit_trail.jsonl", audit_trail)

            zf.writestr(
                "chain_verification.json",
                json.dumps(
                    {
                        "chain_valid": chain_valid,
                        "first_broken_index": first_broken,
                        "total_events": len(events),
                    },
                    indent=2,
                ),
            )

            zf.writestr(
                "signatures.json",
                json.dumps(
                    [
                        {
                            "id": str(s.id),
                            "version_id": str(s.document_version_id),
                            "type": s.signature_type,
                            "status": s.verification_status,
                            "signer_name": s.signer_name,
                            "signer_inn": s.signer_inn,
                        }
                        for s in sig_rows
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
            )

        package_bytes = buf.getvalue()

        package_key = (
            f"{tenant_id}/{document_id}/audit-packages/"
            f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid4()}.zip"
        )
        storage.put_object(package_key, package_bytes, content_type="application/zip")

        doc_repo = DocumentRepository(sf)
        from src.domain.entities.storage_object import StorageObject
        from src.infrastructure.crypto.checksum_service import ChecksumService

        checksum = ChecksumService().compute(package_bytes)
        await doc_repo.create_storage_object(
            StorageObject(
                id=uuid4(),
                tenant_id=UUID(tenant_id),
                object_key=package_key,
                bucket_name=cfg.minio_bucket_documents,
                storage_class=StorageClass.STANDARD,
                encrypted=False,
                object_size=len(package_bytes),
                object_checksum=checksum,
                created_at=datetime.now(UTC),
            )
        )

        audit_repo = AuditRepository(sf, chain)
        last_hash = await audit_repo.get_last_hash("document", UUID(document_id))
        payload = {
            "package_key": package_key,
            "chain_valid": chain_valid,
            "event_count": len(events),
        }
        event_hash = chain.compute_hash(payload, last_hash)
        await audit_repo.create_event(
            AuditEvent(
                id=uuid4(),
                tenant_id=UUID(tenant_id),
                actor_user_id=UUID(requested_by) if requested_by else None,
                resource_type="document",
                resource_id=UUID(document_id),
                event_type=EventType.AUDIT_EXPORTED,
                ip_address=None,
                user_agent="celery:generate_audit_package",
                trace_id=None,
                payload=payload,
                prev_event_hash=last_hash,
                event_hash=event_hash,
                created_at=datetime.now(UTC),
            )
        )

    log.info("audit_package.done", key=package_key, size=len(package_bytes))
    return {"package_key": package_key, "size_bytes": str(len(package_bytes))}
