"""Celery task package — import all tasks so Celery autodiscovery works."""
from src.infrastructure.queue.tasks.apply_watermark_task import apply_watermark_task
from src.infrastructure.queue.tasks.generate_audit_package_task import (
    generate_audit_package_task,
)
from src.infrastructure.queue.tasks.ingest_document_task import ingest_document_task
from src.infrastructure.queue.tasks.legal_hold_monitor_task import monitor_legal_holds
from src.infrastructure.queue.tasks.retention_expiry_scan_task import (
    scan_retention_expiry,
)
from src.infrastructure.queue.tasks.rotate_keys_task import rotate_keys_task
from src.infrastructure.queue.tasks.storage_consistency_check_task import (
    check_storage_consistency,
)
from src.infrastructure.queue.tasks.verify_signature_task import verify_signature_task

__all__ = [
    "apply_watermark_task",
    "check_storage_consistency",
    "generate_audit_package_task",
    "ingest_document_task",
    "monitor_legal_holds",
    "rotate_keys_task",
    "scan_retention_expiry",
    "verify_signature_task",
]
