from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime

from sqlalchemy import select

from src.core.config import get_settings
from src.domain.entities.audit_event import AuditEvent
from src.domain.repositories import IAuditRepository
from src.domain.value_objects import EventType
from src.infrastructure.database.models import AuditEventModel
from src.infrastructure.database.session import AsyncSessionFactory
from src.infrastructure.crypto.integrity_chain import IntegrityChainService


class AuditRepository(IAuditRepository):
    def __init__(
        self,
        session_factory: AsyncSessionFactory,
        integrity_chain: IntegrityChainService,
    ) -> None:
        self._sf = session_factory
        self._chain = integrity_chain

    @staticmethod
    def _to_entity(m: AuditEventModel) -> AuditEvent:
        return AuditEvent(
            id=m.id,
            tenant_id=m.tenant_id,
            actor_user_id=m.actor_user_id,
            resource_type=m.resource_type,
            resource_id=m.resource_id,
            event_type=EventType(m.event_type),
            ip_address=m.ip_address,
            user_agent=m.user_agent,
            trace_id=m.trace_id,
            payload=dict(m.payload or {}),
            prev_event_hash=m.prev_event_hash,
            event_hash=m.event_hash,
            created_at=m.created_at,
        )

    async def create_event(self, event: AuditEvent) -> AuditEvent:
        async with self._sf.session() as session:
            model = AuditEventModel(
                id=event.id,
                tenant_id=event.tenant_id,
                actor_user_id=event.actor_user_id,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                event_type=event.event_type.value,
                ip_address=event.ip_address,
                user_agent=event.user_agent,
                trace_id=event.trace_id,
                payload=event.payload,
                prev_event_hash=event.prev_event_hash,
                event_hash=event.event_hash,
            )
            session.add(model)
            await session.flush()
            return self._to_entity(model)

    async def get_timeline(
        self,
        resource_type: str,
        resource_id: uuid.UUID,
        limit: int = 100,
    ) -> list[AuditEvent]:
        async with self._sf.session() as session:
            result = await session.execute(
                select(AuditEventModel)
                .where(
                    AuditEventModel.resource_type == resource_type,
                    AuditEventModel.resource_id == resource_id,
                )
                .order_by(AuditEventModel.created_at.asc())
                .limit(limit)
            )
            return [self._to_entity(m) for m in result.scalars().all()]

    async def search(
        self,
        tenant_id: uuid.UUID,
        *,
        event_types: list[str] | None = None,
        actor_id: uuid.UUID | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        async with self._sf.session() as session:
            q = (
                select(AuditEventModel)
                .where(AuditEventModel.tenant_id == tenant_id)
                .order_by(AuditEventModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            if event_types:
                q = q.where(AuditEventModel.event_type.in_(event_types))
            if actor_id:
                q = q.where(AuditEventModel.actor_user_id == actor_id)
            if from_dt:
                q = q.where(AuditEventModel.created_at >= from_dt)
            if to_dt:
                q = q.where(AuditEventModel.created_at <= to_dt)
            result = await session.execute(q)
            return [self._to_entity(m) for m in result.scalars().all()]

    async def get_last_hash(self, resource_type: str, resource_id: uuid.UUID) -> str | None:
        async with self._sf.session() as session:
            result = await session.execute(
                select(AuditEventModel.event_hash)
                .where(
                    AuditEventModel.resource_type == resource_type,
                    AuditEventModel.resource_id == resource_id,
                )
                .order_by(AuditEventModel.created_at.desc())
                .limit(1)
            )
            return result.scalars().first()
