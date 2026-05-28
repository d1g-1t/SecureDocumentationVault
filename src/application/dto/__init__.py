"""Application-layer DTOs — Pydantic v2 schemas for commands and queries.

All DTOs are validated at the boundary (FastAPI routers).
Domain entities are NEVER returned directly from routes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# ─── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class CurrentUserDTO(BaseModel):
    user_id: UUID
    tenant_id: UUID
    email: str
    role: str


# ─── Document ─────────────────────────────────────────────────────────────────

class UploadDocumentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    document_type: str = Field(min_length=1, max_length=64)
    retention_policy_id: UUID | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateDocumentRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class DocumentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    title: str
    document_type: str
    status: str
    owner_user_id: UUID
    current_version_id: UUID | None
    retention_policy_id: UUID | None
    legal_hold_active: bool
    tags: list[str]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    versions_count: int = 0


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    limit: int
    offset: int


# ─── Document Version ─────────────────────────────────────────────────────────

class VersionResponse(BaseModel):
    id: UUID
    document_id: UUID
    version_number: int
    file_name: str
    mime_type: str
    size_bytes: int
    sha256_checksum: str
    encryption_key_id: str
    uploaded_by: UUID
    created_at: datetime


# ─── Signature ────────────────────────────────────────────────────────────────

class VerifySignatureRequest(BaseModel):
    signature_type: Literal["KEP", "NEP", "CMS", "PEP"] = "CMS"
    detached_signature_b64: str | None = None


class SignatureReportResponse(BaseModel):
    id: UUID
    document_version_id: UUID
    signature_type: str
    verification_status: str
    signer_name: str | None
    signer_inn: str | None
    certificate_subject: str | None
    certificate_issuer: str | None
    certificate_serial: str | None
    signing_time: datetime | None
    signature_hash: str | None
    raw_report: dict[str, Any]
    verified_at: datetime | None


# ─── Share Links ──────────────────────────────────────────────────────────────

class CreateShareLinkRequest(BaseModel):
    expires_at: datetime
    max_downloads: int | None = Field(default=None, ge=1)
    password: str | None = None
    watermark_on_download: bool = True

    @model_validator(mode="after")
    def validate_expiry(self) -> "CreateShareLinkRequest":
        from datetime import UTC
        from datetime import datetime as dt

        if self.expires_at <= dt.now(UTC):
            raise ValueError("expires_at must be in the future")
        return self


class ShareLinkResponse(BaseModel):
    id: UUID
    document_id: UUID
    expires_at: datetime
    max_downloads: int | None
    download_count: int
    watermark_on_download: bool
    revoked_at: datetime | None
    created_at: datetime
    is_active: bool


class PublicShareDownloadRequest(BaseModel):
    password: str | None = None


# ─── Retention ────────────────────────────────────────────────────────────────

class CreateRetentionPolicyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    retention_mode: Literal["GOVERNANCE", "COMPLIANCE"]
    retention_days: int = Field(ge=1)
    allow_delete_after_expiry: bool = False
    description: str | None = None


class RetentionPolicyResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    retention_mode: str
    retention_days: int
    allow_delete_after_expiry: bool
    description: str | None
    created_at: datetime


class ApplyRetentionPolicyRequest(BaseModel):
    retention_policy_id: UUID


# ─── Legal Hold ───────────────────────────────────────────────────────────────

class PlaceLegalHoldRequest(BaseModel):
    document_id: UUID
    reason: str = Field(min_length=10)


class LegalHoldResponse(BaseModel):
    id: UUID
    document_id: UUID
    reason: str
    placed_by: UUID
    active: bool
    placed_at: datetime
    released_at: datetime | None


# ─── Audit ────────────────────────────────────────────────────────────────────

class AuditEventResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    actor_user_id: UUID | None
    resource_type: str
    resource_id: UUID
    event_type: str
    ip_address: str | None
    trace_id: str | None
    payload: dict[str, Any]
    event_hash: str
    created_at: datetime


class AuditSearchRequest(BaseModel):
    event_types: list[str] | None = None
    actor_id: UUID | None = None
    from_dt: datetime | None = None
    to_dt: datetime | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


# ─── Search ───────────────────────────────────────────────────────────────────

class DocumentSearchRequest(BaseModel):
    query: str | None = None
    status: str | None = None
    tags: list[str] | None = None
    document_type: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


# ─── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    checks: dict[str, str]
