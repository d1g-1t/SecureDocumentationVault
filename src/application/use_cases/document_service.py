from __future__ import annotations

import uuid
from datetime import UTC, datetime

from src.application.dto import (
    DocumentResponse,
    UploadDocumentRequest,
    VersionResponse,
)
from src.core.logging import get_logger
from src.core.config import get_settings
from src.domain.entities.audit_event import AuditEvent
from src.domain.entities.document import Document, DocumentVersion
from src.domain.entities.storage_object import StorageObject
from src.domain.exceptions.domain_exceptions import (
    DocumentNotFoundError,
    LegalHoldViolationError,
)
from src.domain.repositories import (
    IAuditRepository,
    IDocumentRepository,
    ILegalHoldRepository,
    IRetentionRepository,
)
from src.domain.value_objects import DocumentStatus, EventType, StorageClass
from src.infrastructure.crypto.checksum_service import ChecksumService
from src.infrastructure.crypto.envelope_encryption import EnvelopeEncryptionService
from src.infrastructure.crypto.integrity_chain import IntegrityChainService
from src.infrastructure.observability.metrics import documents_uploaded_total, document_versions_total
from src.infrastructure.storage.minio_storage import MinioStorage

logger = get_logger(__name__)


class DocumentService:

    def __init__(
        self,
        document_repo: IDocumentRepository,
        audit_repo: IAuditRepository,
        legal_hold_repo: ILegalHoldRepository,
        retention_repo: IRetentionRepository,
        storage: MinioStorage,
        encryption: EnvelopeEncryptionService,
        checksum_svc: ChecksumService,
        integrity_chain: IntegrityChainService,
    ) -> None:
        self._docs = document_repo
        self._audit = audit_repo
        self._holds = legal_hold_repo
        self._retention = retention_repo
        self._storage = storage
        self._enc = encryption
        self._checksum = checksum_svc
        self._chain = integrity_chain

    async def upload_document(
        self,
        request: UploadDocumentRequest,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        tenant_id: uuid.UUID,
        actor_id: uuid.UUID,
        ip_address: str | None,
        trace_id: str | None,
    ) -> DocumentResponse:

        doc_id = uuid.uuid4()
        version_id = uuid.uuid4()

        dek, enc_key_id = self._enc.generate_dek()
        encrypted_bytes = self._enc.encrypt_bytes(file_bytes, dek)
        checksum = self._checksum.compute(file_bytes)

        object_key = MinioStorage.build_object_key(tenant_id, doc_id, version_id, file_name)
        self._storage.put_object(object_key, encrypted_bytes, content_type=mime_type)

        cfg = get_settings()
        storage_obj = await self._docs.create_storage_object(
            StorageObject(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                object_key=object_key,
                bucket_name=cfg.minio_bucket_documents,
                storage_class=StorageClass(cfg.default_storage_class),
                encrypted=True,
                object_size=len(encrypted_bytes),
                object_checksum=self._checksum.compute(encrypted_bytes),
                created_at=datetime.now(UTC),
            )
        )

        document = await self._docs.create(
            Document(
                id=doc_id,
                tenant_id=tenant_id,
                title=request.title,
                document_type=request.document_type,
                status=DocumentStatus.PROCESSING,
                owner_user_id=actor_id,
                current_version_id=None,
                retention_policy_id=request.retention_policy_id,
                legal_hold_active=False,
                tags=request.tags,
                metadata=request.metadata,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

        version = await self._docs.create_version(
            DocumentVersion(
                id=version_id,
                document_id=doc_id,
                version_number=1,
                file_name=file_name,
                mime_type=mime_type,
                size_bytes=len(file_bytes),
                sha256_checksum=checksum,
                storage_object_id=storage_obj.id,
                encryption_key_id=enc_key_id,
                uploaded_by=actor_id,
                created_at=datetime.now(UTC),
            )
        )

        document.status = DocumentStatus.ACTIVE
        document.current_version_id = version.id
        document = await self._docs.update(document)

        await self._write_audit(
            tenant_id=tenant_id,
            actor_id=actor_id,
            resource_id=doc_id,
            resource_type="document",
            event_type=EventType.DOCUMENT_CREATED,
            payload={"title": request.title, "version_id": str(version_id)},
            ip_address=ip_address,
            trace_id=trace_id,
        )

        documents_uploaded_total.labels(
            tenant_id=str(tenant_id), document_type=request.document_type
        ).inc()

        logger.info(
            "document_uploaded",
            doc_id=str(doc_id),
            tenant_id=str(tenant_id),
            size_bytes=len(file_bytes),
        )

        return self._map_to_response(document)

    async def download_document(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
        actor_id: uuid.UUID,
        ip_address: str | None,
        trace_id: str | None,
    ) -> tuple[bytes, str, str]:
        document = await self._get_or_raise(document_id, tenant_id)

        if not document.current_version_id:
            raise DocumentNotFoundError(document_id)

        version = await self._docs.get_version_by_id(document.current_version_id)
        if not version:
            raise DocumentNotFoundError(document_id)

        object_key = MinioStorage.build_object_key(
            tenant_id, document_id, version.id, version.file_name
        )
        encrypted_bytes = self._storage.get_object(object_key)
        dek = self._enc.unwrap_dek(version.encryption_key_id)
        plain_bytes = self._enc.decrypt_bytes(encrypted_bytes, dek)

        await self._write_audit(
            tenant_id=tenant_id,
            actor_id=actor_id,
            resource_id=document_id,
            resource_type="document",
            event_type=EventType.DOCUMENT_DOWNLOADED,
            payload={"version_id": str(version.id)},
            ip_address=ip_address,
            trace_id=trace_id,
        )

        return plain_bytes, version.file_name, version.mime_type

    async def download_public(
        self,
        document_id: uuid.UUID,
    ) -> tuple[bytes, str, str]:
        document = await self._docs.get_by_id_global(document_id)
        if not document:
            raise DocumentNotFoundError(document_id)

        if not document.current_version_id:
            raise DocumentNotFoundError(document_id)

        version = await self._docs.get_version_by_id(document.current_version_id)
        if not version:
            raise DocumentNotFoundError(document_id)

        object_key = MinioStorage.build_object_key(
            document.tenant_id, document_id, version.id, version.file_name
        )
        encrypted_bytes = self._storage.get_object(object_key)
        dek = self._enc.unwrap_dek(version.encryption_key_id)
        plain_bytes = self._enc.decrypt_bytes(encrypted_bytes, dek)

        return plain_bytes, version.file_name, version.mime_type

    async def delete_document(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
        actor_id: uuid.UUID,
        privileged_purge: bool,
        ip_address: str | None,
        trace_id: str | None,
    ) -> None:
        document = await self._get_or_raise(document_id, tenant_id)

        if document.legal_hold_active and not privileged_purge:
            raise LegalHoldViolationError(document_id)

        if document.retention_policy_id:
            policy = await self._retention.get_policy(document.retention_policy_id)
            if policy:
                allowed, reason = policy.can_delete(document.created_at)
                if not allowed and not privileged_purge:
                    from src.domain.exceptions.domain_exceptions import RetentionPolicyViolationError
                    raise RetentionPolicyViolationError(reason)

        document.soft_delete()
        await self._docs.update(document)

        await self._write_audit(
            tenant_id=tenant_id,
            actor_id=actor_id,
            resource_id=document_id,
            resource_type="document",
            event_type=EventType.DOCUMENT_DELETED,
            payload={"privileged_purge": privileged_purge},
            ip_address=ip_address,
            trace_id=trace_id,
        )

    async def restore_document(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
        actor_id: uuid.UUID,
        ip_address: str | None,
        trace_id: str | None,
    ) -> DocumentResponse:
        document = await self._get_or_raise(document_id, tenant_id)
        document.restore()
        document = await self._docs.update(document)

        await self._write_audit(
            tenant_id=tenant_id,
            actor_id=actor_id,
            resource_id=document_id,
            resource_type="document",
            event_type=EventType.DOCUMENT_RESTORED,
            payload={},
            ip_address=ip_address,
            trace_id=trace_id,
        )

        return self._map_to_response(document)

    async def get_document(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> DocumentResponse:
        doc = await self._get_or_raise(document_id, tenant_id)
        return self._map_to_response(doc)

    async def list_documents(
        self,
        tenant_id: uuid.UUID,
        status: DocumentStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[DocumentResponse], int]:
        documents = await self._docs.list_by_tenant(
            tenant_id, status=status, limit=limit, offset=offset
        )
        return [self._map_to_response(d) for d in documents], len(documents)

    async def list_versions(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[VersionResponse]:
        await self._get_or_raise(document_id, tenant_id)
        versions = await self._docs.list_versions(document_id)
        return [
            VersionResponse(
                id=v.id,
                document_id=v.document_id,
                version_number=v.version_number,
                file_name=v.file_name,
                mime_type=v.mime_type,
                size_bytes=v.size_bytes,
                sha256_checksum=v.sha256_checksum,
                encryption_key_id=v.encryption_key_id,
                uploaded_by=v.uploaded_by,
                created_at=v.created_at,
            )
            for v in versions
        ]

    async def update_document(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
        actor_id: uuid.UUID,
        title: str | None,
        tags: list[str] | None,
        metadata: dict | None,
        ip_address: str | None,
        trace_id: str | None,
    ) -> DocumentResponse:
        document = await self._get_or_raise(document_id, tenant_id)

        changes: dict[str, object] = {}
        if title is not None:
            document.title = title
            changes["title"] = title
        if tags is not None:
            document.tags = tags
            changes["tags"] = tags
        if metadata is not None:
            document.metadata = metadata
            changes["metadata"] = metadata

        document.updated_at = datetime.now(UTC)
        document = await self._docs.update(document)

        await self._write_audit(
            tenant_id=tenant_id,
            actor_id=actor_id,
            resource_id=document_id,
            resource_type="document",
            event_type=EventType.DOCUMENT_UPDATED,
            payload=changes,
            ip_address=ip_address,
            trace_id=trace_id,
        )

        return self._map_to_response(document)

    async def verify_integrity(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> dict:
        await self._get_or_raise(document_id, tenant_id)
        events = await self._audit.get_timeline("document", document_id, limit=10000)

        chain_data = [
            {
                "payload": e.payload,
                "prev_event_hash": e.prev_event_hash,
                "event_hash": e.event_hash,
            }
            for e in events
        ]

        is_valid, broken_idx = self._chain.verify_chain(chain_data)
        return {
            "document_id": str(document_id),
            "chain_length": len(chain_data),
            "is_valid": is_valid,
            "broken_at_index": broken_idx,
        }

    async def _get_or_raise(
        self, document_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Document:
        doc = await self._docs.get_by_id(document_id, tenant_id)
        if not doc:
            raise DocumentNotFoundError(document_id)
        return doc

    async def _write_audit(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_id: uuid.UUID,
        resource_id: uuid.UUID,
        resource_type: str,
        event_type: EventType,
        payload: dict[str, object],
        ip_address: str | None,
        trace_id: str | None,
    ) -> None:
        prev_hash = await self._audit.get_last_hash(resource_type, resource_id)
        event_hash = self._chain.compute_hash(payload, prev_hash)

        await self._audit.create_event(
            AuditEvent(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                actor_user_id=actor_id,
                resource_type=resource_type,
                resource_id=resource_id,
                event_type=event_type,
                ip_address=ip_address,
                user_agent=None,
                trace_id=trace_id,
                payload=payload,
                prev_event_hash=prev_hash,
                event_hash=event_hash,
                created_at=datetime.now(UTC),
            )
        )

    @staticmethod
    def _map_to_response(doc: Document) -> DocumentResponse:
        return DocumentResponse(
            id=doc.id,
            tenant_id=doc.tenant_id,
            title=doc.title,
            document_type=doc.document_type,
            status=doc.status.value,
            owner_user_id=doc.owner_user_id,
            current_version_id=doc.current_version_id,
            retention_policy_id=doc.retention_policy_id,
            legal_hold_active=doc.legal_hold_active,
            tags=doc.tags,
            metadata=doc.metadata,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            versions_count=len(doc.versions),
        )
