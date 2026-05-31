"""Repository interfaces — hexagonal port definitions.

Concrete implementations live in infrastructure/database/repositories/.
Domain code depends only on these interfaces.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.domain.entities.audit_event import AuditEvent
from src.domain.entities.document import Document, DocumentVersion
from src.domain.entities.retention_policy import LegalHold, RetentionPolicy
from src.domain.entities.share_link import ShareLink
from src.domain.entities.signature_record import SignatureRecord
from src.domain.entities.storage_object import StorageObject
from src.domain.value_objects import DocumentStatus


class IDocumentRepository(ABC):
    @abstractmethod
    async def get_by_id(self, document_id: UUID, tenant_id: UUID) -> Document | None: ...

    @abstractmethod
    async def get_by_id_global(self, document_id: UUID) -> Document | None:
        """Get document by ID without tenant scoping (for public share downloads)."""
        ...

    @abstractmethod
    async def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        status: DocumentStatus | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Document]: ...

    @abstractmethod
    async def create(self, document: Document) -> Document: ...

    @abstractmethod
    async def update(self, document: Document) -> Document: ...

    @abstractmethod
    async def list_versions(self, document_id: UUID) -> list[DocumentVersion]: ...

    @abstractmethod
    async def get_version_by_id(self, version_id: UUID) -> DocumentVersion | None: ...

    @abstractmethod
    async def create_version(self, version: DocumentVersion) -> DocumentVersion: ...

    @abstractmethod
    async def create_storage_object(self, obj: StorageObject) -> StorageObject:
        """Persist a storage-object record (one per encrypted blob in MinIO)."""
        ...

    @abstractmethod
    async def link_version_storage(
        self, version_id: UUID, storage_object_id: UUID
    ) -> None:
        """Atomically set DocumentVersion.storage_object_id."""
        ...


class ISignatureRepository(ABC):
    @abstractmethod
    async def create(self, record: SignatureRecord) -> SignatureRecord: ...

    @abstractmethod
    async def get_by_version(self, version_id: UUID) -> list[SignatureRecord]: ...

    @abstractmethod
    async def get_by_id(self, record_id: UUID) -> SignatureRecord | None: ...


class IAuditRepository(ABC):
    @abstractmethod
    async def create_event(self, event: AuditEvent) -> AuditEvent: ...

    @abstractmethod
    async def get_timeline(
        self,
        resource_type: str,
        resource_id: UUID,
        limit: int = 100,
    ) -> list[AuditEvent]: ...

    @abstractmethod
    async def search(
        self,
        tenant_id: UUID,
        *,
        event_types: list[str] | None = None,
        actor_id: UUID | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]: ...

    @abstractmethod
    async def get_last_hash(self, resource_type: str, resource_id: UUID) -> str | None: ...


class IShareRepository(ABC):
    @abstractmethod
    async def create(self, share: ShareLink) -> ShareLink: ...

    @abstractmethod
    async def get_by_id(self, share_id: UUID) -> ShareLink | None: ...

    @abstractmethod
    async def get_by_token_hash(self, token_hash: str) -> ShareLink | None: ...

    @abstractmethod
    async def list_by_document(self, document_id: UUID) -> list[ShareLink]: ...

    @abstractmethod
    async def update(self, share: ShareLink) -> ShareLink: ...


class IRetentionRepository(ABC):
    @abstractmethod
    async def create_policy(self, policy: RetentionPolicy) -> RetentionPolicy: ...

    @abstractmethod
    async def get_policy(self, policy_id: UUID) -> RetentionPolicy | None: ...

    @abstractmethod
    async def list_policies(self, tenant_id: UUID) -> list[RetentionPolicy]: ...


class ILegalHoldRepository(ABC):
    @abstractmethod
    async def create(self, hold: LegalHold) -> LegalHold: ...

    @abstractmethod
    async def get_by_id(self, hold_id: UUID) -> LegalHold | None: ...

    @abstractmethod
    async def list_active_by_document(self, document_id: UUID) -> list[LegalHold]: ...

    @abstractmethod
    async def update(self, hold: LegalHold) -> LegalHold: ...
