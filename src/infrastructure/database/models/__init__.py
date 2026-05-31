"""SQLAlchemy 2 ORM models — exact match for the SQL schema.

All models use:
 - UUID primary keys from gen_random_uuid()
 - TIMESTAMPTZ (timezone=True) for all timestamps
 - JSONB for flexible metadata / reports
 - Relationship loading strategy: selectin (avoids N+1 by default)
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.base import Base, TimestampMixin, UUIDPrimaryKey


# ─── Tenant ──────────────────────────────────────────────────────────────────

class TenantModel(UUIDPrimaryKey, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    users: Mapped[list["ApiUserModel"]] = relationship(
        back_populates="tenant", lazy="noload"
    )


# ─── User ─────────────────────────────────────────────────────────────────────

class ApiUserModel(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "api_users"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped["TenantModel"] = relationship(back_populates="users", lazy="selectin")


# ─── Retention Policy ─────────────────────────────────────────────────────────

class RetentionPolicyModel(UUIDPrimaryKey, Base):
    __tablename__ = "retention_policies"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    retention_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    allow_delete_after_expiry: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )


# ─── Document ─────────────────────────────────────────────────────────────────

class DocumentModel(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "documents"

    __table_args__ = (
        Index("idx_documents_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("api_users.id"), nullable=False
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("document_versions.id", use_alter=True, name="fk_documents_current_version"),
        nullable=True,
    )
    retention_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("retention_policies.id"),
        nullable=True,
    )
    legal_hold_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tags: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default="'[]'")
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, server_default="'{}'"
    )

    # Relationships — selectin avoids N+1 on list endpoints
    versions: Mapped[list["DocumentVersionModel"]] = relationship(
        "DocumentVersionModel",
        back_populates="document",
        foreign_keys="DocumentVersionModel.document_id",
        lazy="selectin",
        order_by="DocumentVersionModel.version_number",
    )
    retention_policy: Mapped["RetentionPolicyModel | None"] = relationship(lazy="selectin")
    legal_holds: Mapped[list["LegalHoldModel"]] = relationship(
        back_populates="document", lazy="noload"
    )
    share_links: Mapped[list["ShareLinkModel"]] = relationship(
        back_populates="document", lazy="noload"
    )


# ─── Document Version ─────────────────────────────────────────────────────────

class DocumentVersionModel(UUIDPrimaryKey, Base):
    __tablename__ = "document_versions"

    __table_args__ = (
        UniqueConstraint("document_id", "version_number"),
        Index("idx_document_versions_doc", "document_id", "version_number"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_object_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("storage_objects.id", use_alter=True, name="fk_versions_storage_object"),
        nullable=True,
    )
    encryption_key_id: Mapped[str] = mapped_column(String(128), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("api_users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    document: Mapped["DocumentModel"] = relationship(
        back_populates="versions",
        foreign_keys=[document_id],
        lazy="noload",
    )
    signatures: Mapped[list["SignatureRecordModel"]] = relationship(
        back_populates="version", lazy="selectin"
    )
    storage_object: Mapped["StorageObjectModel | None"] = relationship(
        foreign_keys=[storage_object_id], lazy="selectin"
    )


# ─── Storage Object ───────────────────────────────────────────────────────────

class StorageObjectModel(UUIDPrimaryKey, Base):
    __tablename__ = "storage_objects"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    object_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    bucket_name: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_class: Mapped[str] = mapped_column(String(32), nullable=False)
    encrypted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    object_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    object_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )


# ─── Signature Record ─────────────────────────────────────────────────────────

class SignatureRecordModel(UUIDPrimaryKey, Base):
    __tablename__ = "signature_records"

    __table_args__ = (
        Index("idx_signature_records_status", "verification_status"),
    )

    document_version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    signature_type: Mapped[str] = mapped_column(String(32), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False)
    signer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signer_inn: Mapped[str | None] = mapped_column(String(12), nullable=True)
    certificate_subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    certificate_issuer: Mapped[str | None] = mapped_column(Text, nullable=True)
    certificate_serial: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signing_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signature_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_report: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="'{}'"
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    version: Mapped["DocumentVersionModel"] = relationship(
        back_populates="signatures", lazy="noload"
    )


# ─── Share Link ───────────────────────────────────────────────────────────────

class ShareLinkModel(UUIDPrimaryKey, Base):
    __tablename__ = "share_links"

    __table_args__ = (
        Index("idx_share_links_expiry", "expires_at", "revoked_at"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("api_users.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_downloads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    watermark_on_download: Mapped[bool] = mapped_column(Boolean, default=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    document: Mapped["DocumentModel"] = relationship(back_populates="share_links", lazy="noload")


# ─── Legal Hold ───────────────────────────────────────────────────────────────

class LegalHoldModel(UUIDPrimaryKey, Base):
    __tablename__ = "legal_holds"

    __table_args__ = (
        Index("idx_legal_holds_active", "document_id", "active"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    placed_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("api_users.id"), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    placed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped["DocumentModel"] = relationship(back_populates="legal_holds", lazy="noload")


# ─── Audit Event ──────────────────────────────────────────────────────────────

class AuditEventModel(UUIDPrimaryKey, Base):
    __tablename__ = "audit_events"

    __table_args__ = (
        Index("idx_audit_events_resource", "resource_type", "resource_id", "created_at"),
        Index("idx_audit_events_trace", "trace_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("api_users.id"), nullable=True
    )
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="'{}'"
    )
    prev_event_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )


# ─── Watermark Profile ────────────────────────────────────────────────────────

class WatermarkProfileModel(UUIDPrimaryKey, Base):
    __tablename__ = "watermark_profiles"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="'{}'"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )
