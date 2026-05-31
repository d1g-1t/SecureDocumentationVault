from __future__ import annotations

import structlog
from sqlalchemy import select

from src.infrastructure.database.models import StorageObjectModel
from src.infrastructure.database.session import AsyncSessionFactory
from src.infrastructure.observability.metrics import storage_consistency_failures_total
from src.infrastructure.queue.celery_app import celery_app
from src.infrastructure.queue.tasks._async_bridge import run_sync
from src.infrastructure.storage.minio_storage import MinioStorage

log = structlog.get_logger(__name__)


@celery_app.task(
    name="src.infrastructure.queue.tasks.storage_consistency_check_task.check_storage_consistency",
    queue="vault.retention",
    bind=True,
    acks_late=True,
)
def check_storage_consistency(self: object) -> dict[str, int]:
    return run_sync(_check())


async def _check() -> dict[str, int]:
    log.info("storage_consistency.start")

    sf = AsyncSessionFactory()
    storage = MinioStorage()

    async with sf.session() as session:
        rows = (await session.scalars(select(StorageObjectModel))).all()

    ghosts = 0
    by_tenant: dict[str, int] = {}

    for row in rows:
        if not storage.object_exists(row.object_key):
            ghosts += 1
            tid = str(row.tenant_id)
            by_tenant[tid] = by_tenant.get(tid, 0) + 1
            log.error("storage_consistency.ghost", object_key=row.object_key)

    for tid, count in by_tenant.items():
        storage_consistency_failures_total.labels(tenant_id=tid).inc(count)

    log.info("storage_consistency.done", total_rows=len(rows), ghosts=ghosts)
    return {"total_rows": len(rows), "ghosts": ghosts}
