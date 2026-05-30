from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import structlog
from sqlalchemy import select

from src.domain.entities.audit_event import AuditEvent
from src.domain.value_objects import EventType
from src.infrastructure.crypto.integrity_chain import IntegrityChainService
from src.infrastructure.database.models import DocumentModel, LegalHoldModel
from src.infrastructure.database.repositories.audit_repository import AuditRepository
from src.infrastructure.database.session import AsyncSessionFactory
from src.infrastructure.observability.metrics import legal_holds_active
from src.infrastructure.queue.celery_app import celery_app
from src.infrastructure.queue.tasks._async_bridge import run_sync

log = structlog.get_logger(__name__)


@celery_app.task(
    name="src.infrastructure.queue.tasks.legal_hold_monitor_task.monitor_legal_holds",
    queue="vault.retention",
    bind=True,
    acks_late=True,
)
def monitor_legal_holds(self: object) -> dict[str, int]:
    return run_sync(_monitor())


async def _monitor() -> dict[str, int]:
    log.info("legal_hold_monitor.start")

    sf = AsyncSessionFactory()
    chain = IntegrityChainService()
    audit_repo = AuditRepository(sf, chain)

    inconsistent = 0
    deleted_under_hold = 0
    now = datetime.now(UTC)

    async with sf.session() as session:
        active_holds = (
            await session.scalars(
                select(LegalHoldModel).where(LegalHoldModel.active.is_(True))
            )
        ).all()

        tenant_counts: dict[str, int] = {}
        for hold in active_holds:
            doc = await session.scalar(
                select(DocumentModel).where(DocumentModel.id == hold.document_id)
            )
            if doc is None:
                continue

            tenant_counts[str(doc.tenant_id)] = tenant_counts.get(str(doc.tenant_id), 0) + 1

            if doc.status == "DELETED":
                deleted_under_hold += 1
                last = await audit_repo.get_last_hash("document", doc.id)
                payload = {
                    "hold_id": str(hold.id),
                    "issue": "document deleted while under active legal hold",
                }
                ev_hash = chain.compute_hash(payload, last)
                await audit_repo.create_event(
                    AuditEvent(
                        id=uuid4(),
                        tenant_id=doc.tenant_id,
                        actor_user_id=None,
                        resource_type="document",
                        resource_id=doc.id,
                        event_type=EventType.INTEGRITY_CHECK_FAILED,
                        ip_address=None,
                        user_agent="celery:legal_hold_monitor",
                        trace_id=None,
                        payload=payload,
                        prev_event_hash=last,
                        event_hash=ev_hash,
                        created_at=now,
                    )
                )

            if not doc.legal_hold_active:
                inconsistent += 1

        for tid, count in tenant_counts.items():
            legal_holds_active.labels(tenant_id=tid).set(count)

    log.info(
        "legal_hold_monitor.done",
        active=len(active_holds),
        inconsistent=inconsistent,
        deleted_under_hold=deleted_under_hold,
    )
    return {
        "active": len(active_holds),
        "inconsistent": inconsistent,
        "deleted_under_hold": deleted_under_hold,
    }
