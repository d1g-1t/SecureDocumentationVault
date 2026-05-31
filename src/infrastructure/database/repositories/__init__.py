"""ShareRepository, RetentionRepository, LegalHoldRepository.

Note: AuditRepository, DocumentRepository, and SignatureRepository live in
their own modules but are also re-exported here for convenience.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from src.domain.entities.retention_policy import LegalHold, RetentionPolicy
from src.domain.entities.share_link import ShareLink
from src.domain.repositories import ILegalHoldRepository, IRetentionRepository, IShareRepository
from src.domain.value_objects import RetentionMode
from src.infrastructure.database.models import (
    LegalHoldModel,
    RetentionPolicyModel,
    ShareLinkModel,
)
from src.infrastructure.database.session import AsyncSessionFactory


# ─── ShareRepository ─────────────────────────────────────────────────────────

class ShareRepository(IShareRepository):
    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._sf = session_factory

    @staticmethod
    def _to_entity(m: ShareLinkModel) -> ShareLink:
        return ShareLink(
            id=m.id,
            document_id=m.document_id,
            created_by=m.created_by,
            token_hash=m.token_hash,
            expires_at=m.expires_at,
            max_downloads=m.max_downloads,
            download_count=m.download_count,
            password_hash=m.password_hash,
            watermark_on_download=m.watermark_on_download,
            revoked_at=m.revoked_at,
            created_at=m.created_at,
        )

    async def create(self, share: ShareLink) -> ShareLink:
        async with self._sf.session() as session:
            model = ShareLinkModel(
                id=share.id,
                document_id=share.document_id,
                created_by=share.created_by,
                token_hash=share.token_hash,
                expires_at=share.expires_at,
                max_downloads=share.max_downloads,
                download_count=share.download_count,
                password_hash=share.password_hash,
                watermark_on_download=share.watermark_on_download,
                revoked_at=share.revoked_at,
            )
            session.add(model)
            await session.flush()
            await session.refresh(model)
            return self._to_entity(model)

    async def get_by_id(self, share_id: uuid.UUID) -> ShareLink | None:
        async with self._sf.session() as session:
            result = await session.execute(
                select(ShareLinkModel).where(ShareLinkModel.id == share_id)
            )
            m = result.scalars().first()
            return self._to_entity(m) if m else None

    async def get_by_token_hash(self, token_hash: str) -> ShareLink | None:
        async with self._sf.session() as session:
            result = await session.execute(
                select(ShareLinkModel).where(ShareLinkModel.token_hash == token_hash)
            )
            m = result.scalars().first()
            return self._to_entity(m) if m else None

    async def list_by_document(self, document_id: uuid.UUID) -> list[ShareLink]:
        async with self._sf.session() as session:
            result = await session.execute(
                select(ShareLinkModel)
                .where(ShareLinkModel.document_id == document_id)
                .order_by(ShareLinkModel.created_at.desc())
            )
            return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, share: ShareLink) -> ShareLink:
        async with self._sf.session() as session:
            result = await session.execute(
                select(ShareLinkModel).where(ShareLinkModel.id == share.id)
            )
            model = result.scalars().one()
            model.download_count = share.download_count
            model.revoked_at = share.revoked_at
            await session.flush()
            await session.refresh(model)
            return self._to_entity(model)


# ─── RetentionRepository ─────────────────────────────────────────────────────

class RetentionRepository(IRetentionRepository):
    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._sf = session_factory

    @staticmethod
    def _to_entity(m: RetentionPolicyModel) -> RetentionPolicy:
        return RetentionPolicy(
            id=m.id,
            tenant_id=m.tenant_id,
            name=m.name,
            retention_mode=RetentionMode(m.retention_mode),
            retention_days=m.retention_days,
            allow_delete_after_expiry=m.allow_delete_after_expiry,
            description=m.description,
            created_at=m.created_at,
        )

    async def create_policy(self, policy: RetentionPolicy) -> RetentionPolicy:
        async with self._sf.session() as session:
            model = RetentionPolicyModel(
                id=policy.id,
                tenant_id=policy.tenant_id,
                name=policy.name,
                retention_mode=policy.retention_mode.value,
                retention_days=policy.retention_days,
                allow_delete_after_expiry=policy.allow_delete_after_expiry,
                description=policy.description,
            )
            session.add(model)
            await session.flush()
            await session.refresh(model)
            return self._to_entity(model)

    async def get_policy(self, policy_id: uuid.UUID) -> RetentionPolicy | None:
        async with self._sf.session() as session:
            result = await session.execute(
                select(RetentionPolicyModel).where(RetentionPolicyModel.id == policy_id)
            )
            m = result.scalars().first()
            return self._to_entity(m) if m else None

    async def list_policies(self, tenant_id: uuid.UUID) -> list[RetentionPolicy]:
        async with self._sf.session() as session:
            result = await session.execute(
                select(RetentionPolicyModel)
                .where(RetentionPolicyModel.tenant_id == tenant_id)
                .order_by(RetentionPolicyModel.created_at.desc())
            )
            return [self._to_entity(m) for m in result.scalars().all()]


# ─── LegalHoldRepository ─────────────────────────────────────────────────────

class LegalHoldRepository(ILegalHoldRepository):
    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._sf = session_factory

    @staticmethod
    def _to_entity(m: LegalHoldModel) -> LegalHold:
        return LegalHold(
            id=m.id,
            document_id=m.document_id,
            reason=m.reason,
            placed_by=m.placed_by,
            active=m.active,
            placed_at=m.placed_at,
            released_at=m.released_at,
        )

    async def create(self, hold: LegalHold) -> LegalHold:
        async with self._sf.session() as session:
            model = LegalHoldModel(
                id=hold.id,
                document_id=hold.document_id,
                reason=hold.reason,
                placed_by=hold.placed_by,
                active=hold.active,
                placed_at=hold.placed_at,
            )
            session.add(model)
            await session.flush()
            await session.refresh(model)
            return self._to_entity(model)

    async def get_by_id(self, hold_id: uuid.UUID) -> LegalHold | None:
        async with self._sf.session() as session:
            result = await session.execute(
                select(LegalHoldModel).where(LegalHoldModel.id == hold_id)
            )
            m = result.scalars().first()
            return self._to_entity(m) if m else None

    async def list_active_by_document(self, document_id: uuid.UUID) -> list[LegalHold]:
        async with self._sf.session() as session:
            result = await session.execute(
                select(LegalHoldModel).where(
                    LegalHoldModel.document_id == document_id,
                    LegalHoldModel.active == True,  # noqa: E712
                )
            )
            return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, hold: LegalHold) -> LegalHold:
        async with self._sf.session() as session:
            result = await session.execute(
                select(LegalHoldModel).where(LegalHoldModel.id == hold.id)
            )
            model = result.scalars().one()
            model.active = hold.active
            model.released_at = hold.released_at
            await session.flush()
            await session.refresh(model)
            return self._to_entity(model)


# ─── Re-exports ──────────────────────────────────────────────────────────────
from src.infrastructure.database.repositories.audit_repository import AuditRepository  # noqa: E402
from src.infrastructure.database.repositories.document_repository import (  # noqa: E402
    DocumentRepository,
)
from src.infrastructure.database.repositories.signature_repository import (  # noqa: E402
    SignatureRepository,
)

__all__ = [
    "AuditRepository",
    "DocumentRepository",
    "LegalHoldRepository",
    "RetentionRepository",
    "ShareRepository",
    "SignatureRepository",
]
