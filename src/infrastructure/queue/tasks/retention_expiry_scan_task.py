from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import structlog
from sqlalchemy import select

from src.domain.entities.audit_event import AuditEvent
from src.domain.value_objects import EventType, RetentionMode
from src.infrastructure.crypto.integrity_chain import IntegrityChainService
from src.infrastructure.database.models import (
    DocumentModel,
    RetentionPolicyModel,
)
from src.infrastructure.database.repositories.audit_repository import AuditRepository
from src.infrastructure.database.session import AsyncSessionFactory
from src.infrastructure.observability.metrics import retention_expiry_total
from src.infrastructure.queue.celery_app import celery_app
from src.infrastructure.queue.tasks._async_bridge import run_sync

log = structlog.get_logger(__name__)


@celery_app.task(
    name="src.infrastructure.queue.tasks.retention_expiry_scan_task.scan_retention_expiry",
    queue="vault.retention",
    bind=True,
    acks_late=True,
)
def scan_retention_expiry(self: object) -> dict[str, int]:
    return run_sync(_scan())


async def _scan() -> dict[str, int]:
    log.info("retention_scan.start")

    sf = AsyncSessionFactory()
    chain = IntegrityChainService()
    audit_repo = AuditRepository(sf, chain)

    expired = 0
    blocked_by_hold = 0
    eligible_for_deletion = 0
    now = datetime.now(UTC)

    async with sf.session() as session:
        rows = (
            await session.scalars(
                select(DocumentModel, RetentionPolicyModel)
                .join(
                    RetentionPolicyModel,
                    DocumentModel.retention_policy_id == RetentionPolicyModel.id,
                )
                .where(DocumentModel.status != "DELETED")
            )
        ).all()

        joined = await session.execute(
            select(DocumentModel, RetentionPolicyModel)
            .join(
                RetentionPolicyModel,
                DocumentModel.retention_policy_id == RetentionPolicyModel.id,
            )
            .where(DocumentModel.status != "DELETED")
        )

        for doc, policy in joined.all():
            expiry = doc.created_at + timedelta(days=policy.retention_days)
            if expiry > now:
                continue
            expired += 1

            if doc.legal_hold_active:
                blocked_by_hold += 1
                retention_expiry_total.labels(action="blocked").inc()
                continue

            mode = RetentionMode(policy.retention_mode)
            if (
                mode == RetentionMode.GOVERNANCE
                or (mode == RetentionMode.COMPLIANCE and policy.allow_delete_after_expiry)
            ):
                eligible_for_deletion += 1
                retention_expiry_total.labels(action="expired").inc()

                last = await audit_repo.get_last_hash("document", doc.id)
                payload = {
                    "retention_policy_id": str(policy.id),
                    "policy_mode": mode.value,
                    "expiry_at": expiry.isoformat(),
                }
                ev_hash = chain.compute_hash(payload, last)
                await audit_repo.create_event(
                    AuditEvent(
                        id=uuid4(),
                        tenant_id=doc.tenant_id,
                        actor_user_id=None,
                        resource_type="document",
                        resource_id=doc.id,
                        event_type=EventType.RETENTION_APPLIED,
                        ip_address=None,
                        user_agent="celery:retention_expiry_scan",
                        trace_id=None,
                        payload=payload,
                        prev_event_hash=last,
                        event_hash=ev_hash,
                        created_at=now,
                    )
                )

    log.info(
        "retention_scan.done",
        expired=expired,
        blocked_by_hold=blocked_by_hold,
        eligible_for_deletion=eligible_for_deletion,
    )
    return {
        "expired": expired,
        "blocked_by_hold": blocked_by_hold,
        "eligible_for_deletion": eligible_for_deletion,
    }
