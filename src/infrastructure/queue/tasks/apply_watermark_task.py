from __future__ import annotations

import io
from uuid import UUID

import structlog
from sqlalchemy import select

from src.infrastructure.crypto.envelope_encryption import EnvelopeEncryptionService
from src.infrastructure.database.models import DocumentVersionModel, StorageObjectModel
from src.infrastructure.database.session import AsyncSessionFactory
from src.infrastructure.queue.celery_app import celery_app
from src.infrastructure.queue.tasks._async_bridge import run_sync
from src.infrastructure.storage.minio_storage import MinioStorage

log = structlog.get_logger(__name__)


@celery_app.task(
    name="vault.ingest.apply_watermark",
    queue="vault.ingest",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    acks_late=True,
)
def apply_watermark_task(
    self: object,
    version_id: str,
    share_id: str,
    watermark_text: str,
) -> dict[str, str]:
    return run_sync(_watermark_async(version_id, share_id, watermark_text))


async def _watermark_async(
    version_id: str,
    share_id: str,
    watermark_text: str,
) -> dict[str, str]:
    log.info("watermark.start", version_id=version_id, share_id=share_id)

    sf = AsyncSessionFactory()
    storage = MinioStorage()
    encryption = EnvelopeEncryptionService()

    async with sf.session() as session:
        version = await session.scalar(
            select(DocumentVersionModel).where(
                DocumentVersionModel.id == UUID(version_id)
            )
        )
        if version is None or version.storage_object_id is None:
            raise ValueError(f"Version {version_id} has no storage object")
        storage_obj = await session.scalar(
            select(StorageObjectModel).where(
                StorageObjectModel.id == version.storage_object_id
            )
        )
        if storage_obj is None:
            raise ValueError(f"Storage object missing for version {version_id}")

    encrypted = storage.get_object(storage_obj.object_key)
    dek = encryption.unwrap_dek(version.encryption_key_id)
    raw = encryption.decrypt_bytes(encrypted, dek)

    watermarked = _stamp_pdf(raw, watermark_text)
    wm_encrypted = encryption.encrypt_bytes(watermarked, dek)

    wm_object_key = f"{storage_obj.object_key}.wm.{share_id}"
    storage.put_object(wm_object_key, wm_encrypted, content_type=version.mime_type)

    log.info("watermark.done", key=wm_object_key)
    return {"watermarked_key": wm_object_key}


def _stamp_pdf(raw_bytes: bytes, text: str) -> bytes:
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import AnnotationBuilder
    except ImportError:
        log.warning("watermark.pypdf_missing")
        return raw_bytes

    try:
        reader = PdfReader(io.BytesIO(raw_bytes))
        writer = PdfWriter()
        for page in reader.pages:
            try:
                annot = AnnotationBuilder.free_text(
                    text=text,
                    rect=(50, 400, 550, 450),
                    font="Helvetica",
                    bold=True,
                    italic=False,
                    font_size="32pt",
                    font_color="ff0000",
                    border_color="ff0000",
                    background_color="ffffff",
                )
                writer.add_page(page)
                writer.add_annotation(page_number=len(writer.pages) - 1, annotation=annot)
            except Exception:
                writer.add_page(page)
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()
    except Exception as exc:
        log.warning("watermark.stamp_failed", error=str(exc))
        return raw_bytes
