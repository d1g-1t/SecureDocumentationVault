from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import structlog
from sqlalchemy import select

from src.domain.entities.audit_event import AuditEvent
from src.domain.value_objects import EventType
from src.infrastructure.crypto.integrity_chain import IntegrityChainService
from src.infrastructure.database.models import StorageObjectModel
from src.infrastructure.database.repositories.audit_repository import AuditRepository
from src.infrastructure.database.session import AsyncSessionFactory
from src.infrastructure.queue.celery_app import celery_app
from src.infrastructure.queue.tasks._async_bridge import run_sync

log = structlog.get_logger(__name__)


@celery_app.task(
    name="vault.crypto.rotate_keys",
    queue="vault.crypto",
    bind=True,
    acks_late=True,
    time_limit=3600,
    soft_time_limit=3500,
)
def rotate_keys_task(self: object, dry_run: bool = True) -> dict[str, int]:
    return run_sync(_rotate(dry_run))


async def _rotate(dry_run: bool) -> dict[str, int]:
    log.info("key_rotation.start", dry_run=dry_run)

    sf = AsyncSessionFactory()
    chain = IntegrityChainService()
    audit_repo = AuditRepository(sf, chain)

    inspected = 0
    now = datetime.now(UTC)

    async with sf.session() as session:
        rows = (await session.scalars(select(StorageObjectModel))).all()

    for row in rows:
        inspected += 1
        last = await audit_repo.get_last_hash("storage_object", row.id)
        payload = {
            "object_key": row.object_key,
            "dry_run": dry_run,
        }
        ev_hash = chain.compute_hash(payload, last)
        await audit_repo.create_event(
            AuditEvent(
                id=uuid4(),
                tenant_id=row.tenant_id,
                actor_user_id=None,
                resource_type="storage_object",
                resource_id=row.id,
                event_type=EventType.KEY_ROTATED,
                ip_address=None,
                user_agent="celery:rotate_keys",
                trace_id=None,
                payload=payload,
                prev_event_hash=last,
                event_hash=ev_hash,
                created_at=now,
            )
        )

    log.info("key_rotation.done", inspected=inspected, dry_run=dry_run)
    return {"inspected": inspected, "dry_run": int(dry_run)}
