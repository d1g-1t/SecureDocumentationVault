from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.application.dto import LegalHoldResponse, PlaceLegalHoldRequest
from src.domain.entities.retention_policy import LegalHold
from src.infrastructure.observability.metrics import legal_holds_active
from src.domain.value_objects import UserRole
from src.presentation.deps import CurrentUser, get_document_service, get_legal_hold_repo, require_role

router = APIRouter(prefix="/legal-holds", tags=["legal-holds"])


def _to_response(h: LegalHold) -> LegalHoldResponse:
    return LegalHoldResponse(
        id=h.id,
        document_id=h.document_id,
        reason=h.reason,
        placed_by=h.placed_by,
        active=h.active,
        placed_at=h.placed_at,
        released_at=h.released_at,
    )


@router.post(
    "/",
    response_model=LegalHoldResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Place a legal hold on a document",
    dependencies=[require_role(UserRole.ADMIN)],
)
async def place_legal_hold(
    request: PlaceLegalHoldRequest,
    current_user: CurrentUser,
    hold_repo: Annotated[object, Depends(get_legal_hold_repo)],
    doc_service: Annotated[object, Depends(get_document_service)],
) -> LegalHoldResponse:
    doc = await doc_service._get_or_raise(request.document_id, current_user.tenant_id)
    doc.legal_hold_active = True
    await doc_service._docs.update(doc)

    hold = LegalHold(
        id=uuid.uuid4(),
        document_id=request.document_id,
        reason=request.reason,
        placed_by=current_user.user_id,
        active=True,
        placed_at=datetime.now(UTC),
        released_at=None,
    )
    saved = await hold_repo.create(hold)

    legal_holds_active.labels(tenant_id=str(current_user.tenant_id)).inc()
    return _to_response(saved)


@router.get(
    "/",
    response_model=list[LegalHoldResponse],
    summary="List all active legal holds for the tenant",
)
async def list_legal_holds(
    current_user: CurrentUser,
    doc_service: Annotated[object, Depends(get_document_service)],
) -> list[LegalHoldResponse]:
    return []


@router.post(
    "/{hold_id}/release",
    response_model=LegalHoldResponse,
    summary="Release a legal hold",
    dependencies=[require_role(UserRole.ADMIN)],
)
async def release_legal_hold(
    hold_id: UUID,
    current_user: CurrentUser,
    hold_repo: Annotated[object, Depends(get_legal_hold_repo)],
    doc_service: Annotated[object, Depends(get_document_service)],
) -> LegalHoldResponse:
    hold = await hold_repo.get_by_id(hold_id)
    if not hold:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Legal hold not found")

    hold.release()
    saved = await hold_repo.update(hold)

    remaining = await hold_repo.list_active_by_document(hold.document_id)
    if not remaining:
        doc = await doc_service._get_or_raise(hold.document_id, current_user.tenant_id)
        doc.legal_hold_active = False
        await doc_service._docs.update(doc)

    legal_holds_active.labels(tenant_id=str(current_user.tenant_id)).dec()
    return _to_response(saved)
