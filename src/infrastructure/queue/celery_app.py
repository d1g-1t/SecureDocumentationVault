from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from src.core.config import get_settings

cfg = get_settings()

celery_app = Celery(
    "securedocvault",
    broker=cfg.celery_broker_url,
    backend=cfg.celery_result_backend,
    include=[
        "src.infrastructure.queue.tasks.ingest_document_task",
        "src.infrastructure.queue.tasks.verify_signature_task",
        "src.infrastructure.queue.tasks.apply_watermark_task",
        "src.infrastructure.queue.tasks.generate_audit_package_task",
        "src.infrastructure.queue.tasks.retention_expiry_scan_task",
        "src.infrastructure.queue.tasks.legal_hold_monitor_task",
        "src.infrastructure.queue.tasks.storage_consistency_check_task",
        "src.infrastructure.queue.tasks.rotate_keys_task",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    result_expires=86400,
    task_routes={
        "src.infrastructure.queue.tasks.ingest_document_task.*": {"queue": "vault.ingest"},
        "src.infrastructure.queue.tasks.verify_signature_task.*": {"queue": "vault.ingest"},
        "src.infrastructure.queue.tasks.apply_watermark_task.*": {"queue": "vault.ingest"},
        "src.infrastructure.queue.tasks.generate_audit_package_task.*": {"queue": "vault.audit"},
        "src.infrastructure.queue.tasks.retention_expiry_scan_task.*": {"queue": "vault.retention"},
        "src.infrastructure.queue.tasks.legal_hold_monitor_task.*": {"queue": "vault.retention"},
        "src.infrastructure.queue.tasks.storage_consistency_check_task.*": {"queue": "vault.retention"},
        "src.infrastructure.queue.tasks.rotate_keys_task.*": {"queue": "vault.crypto"},
    },
    beat_schedule={
        "retention-expiry-scan": {
            "task": "src.infrastructure.queue.tasks.retention_expiry_scan_task.scan_retention_expiry",
            "schedule": crontab(minute="0"),  # every hour
        },
        "storage-consistency-check": {
            "task": "src.infrastructure.queue.tasks.storage_consistency_check_task.check_storage_consistency",
            "schedule": crontab(minute="0", hour="*/6"),  # every 6 hours
        },
        "legal-hold-monitor": {
            "task": "src.infrastructure.queue.tasks.legal_hold_monitor_task.monitor_legal_holds",
            "schedule": crontab(minute="*/30"),  # every 30 minutes
        },
    },
)
