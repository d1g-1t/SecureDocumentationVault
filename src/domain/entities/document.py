"""Document — aggregate root of the vault domain."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from src.domain.value_objects import DocumentStatus


@dataclass
class Document:
    """Aggregate root representing a legally significant document."""

    id: UUID
    tenant_id: UUID
    title: str
    document_type: str
    status: DocumentStatus
    owner_user_id: UUID
    current_version_id: UUID | None
    retention_policy_id: UUID | None
    legal_hold_active: bool
    tags: list[str]
    metadata: dict[str, object]
    created_at: datetime
    updated_at: datetime

    # Loaded eagerly by repository when needed
    versions: list["DocumentVersion"] = field(default_factory=list, repr=False, compare=False)

    def can_be_deleted(self, *, privileged_purge: bool = False) -> tuple[bool, str]:
        """Business rule: check if document may be deleted.

        Returns (allowed, reason).
        """
        if self.legal_hold_active and not privileged_purge:
            return False, "Document is under an active legal hold"
        if self.status == DocumentStatus.DELETED:
            return False, "Document is already deleted"
        return True, ""

    def soft_delete(self) -> None:
        self.status = DocumentStatus.DELETED
        self.updated_at = datetime.now(UTC)

    def restore(self) -> None:
        if self.status != DocumentStatus.DELETED:
            raise ValueError("Only deleted documents can be restored")
        self.status = DocumentStatus.ACTIVE
        self.updated_at = datetime.now(UTC)


@dataclass
class DocumentVersion:
    """Immutable version of a document's file content."""

    id: UUID
    document_id: UUID
    version_number: int
    file_name: str
    mime_type: str
    size_bytes: int
    sha256_checksum: str
    storage_object_id: UUID | None
    encryption_key_id: str
    uploaded_by: UUID
    created_at: datetime
