from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.application.dto import SignatureReportResponse, VerifySignatureRequest
from src.core.logging import get_logger
from src.domain.entities.signature_record import SignatureRecord
from src.domain.value_objects import SignatureStatus, SignatureType, UserRole
from src.infrastructure.observability.metrics import (
    signature_verification_duration,
    signature_verifications_total,
)
from src.infrastructure.signatures.cms_verifier import CmsVerifier
from src.presentation.deps import (
    CurrentUser,
    get_cms_verifier,
    get_document_service,
    get_signature_repo,
    require_role,
)

router = APIRouter(prefix="/versions", tags=["signatures"])
logger = get_logger(__name__)


@router.post(
    "/{version_id}/verify-signature",
    response_model=SignatureReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify a CMS/KEP/NEP signature for a document version",
    dependencies=[require_role(UserRole.AUDITOR)],
)
async def verify_signature(
    version_id: UUID,
    request: VerifySignatureRequest,
    current_user: CurrentUser,
    sig_repo: Annotated[object, Depends(get_signature_repo)],
    doc_service: Annotated[object, Depends(get_document_service)],
    verifier: Annotated[CmsVerifier, Depends(get_cms_verifier)],
) -> SignatureReportResponse:
    from src.infrastructure.database.repositories import SignatureRepository

    assert isinstance(sig_repo, SignatureRepository)

    version = await doc_service._docs.get_version_by_id(version_id)
    if not version:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Version not found")

    encrypted = doc_service._storage.get_object(
        doc_service._storage.build_object_key(
            current_user.tenant_id,
            version.document_id,
            version.id,
            version.file_name,
        )
    )
    dek = doc_service._enc.unwrap_dek(version.encryption_key_id)
    plain_bytes = doc_service._enc.decrypt_bytes(encrypted, dek)

    sig_type = SignatureType(request.signature_type)

    with signature_verification_duration.labels(signature_type=sig_type.value).time():
        report = verifier.verify(
            document_bytes=plain_bytes,
            signature_b64=request.detached_signature_b64 or "",
            signature_type=sig_type,
        )

    status_val = SignatureStatus(report.get("status", SignatureStatus.UNKNOWN.value))

    signature_verifications_total.labels(
        tenant_id=str(current_user.tenant_id),
        signature_type=sig_type.value,
        status=status_val.value,
    ).inc()

    record = SignatureRecord(
        id=uuid.uuid4(),
        document_version_id=version_id,
        signature_type=sig_type,
        verification_status=status_val,
        signer_name=report.get("signer_name"),
        signer_inn=report.get("signer_inn"),
        certificate_subject=report.get("certificate_subject"),
        certificate_issuer=report.get("certificate_issuer"),
        certificate_serial=report.get("certificate_serial"),
        signing_time=None,
        signature_hash=report.get("document_sha256"),
        raw_report=report,
        verified_at=datetime.now(UTC),
    )

    saved = await sig_repo.create(record)

    return SignatureReportResponse(
        id=saved.id,
        document_version_id=saved.document_version_id,
        signature_type=saved.signature_type.value,
        verification_status=saved.verification_status.value,
        signer_name=saved.signer_name,
        signer_inn=saved.signer_inn,
        certificate_subject=saved.certificate_subject,
        certificate_issuer=saved.certificate_issuer,
        certificate_serial=saved.certificate_serial,
        signing_time=saved.signing_time,
        signature_hash=saved.signature_hash,
        raw_report=saved.raw_report,
        verified_at=saved.verified_at,
    )
