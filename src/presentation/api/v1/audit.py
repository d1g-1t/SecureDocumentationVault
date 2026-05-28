from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.application.dto import AuditEventResponse, AuditSearchRequest
from src.domain.entities.audit_event import AuditEvent
from src.domain.value_objects import UserRole
from src.presentation.deps import CurrentUser, get_audit_repo, require_role

router = APIRouter(prefix="/audit", tags=["audit"])


def _to_response(e: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse(
        id=e.id,
        tenant_id=e.tenant_id,
        actor_user_id=e.actor_user_id,
        resource_type=e.resource_type,
        resource_id=e.resource_id,
        event_type=e.event_type.value,
        ip_address=e.ip_address,
        trace_id=e.trace_id,
        payload=e.payload,
        event_hash=e.event_hash,
        created_at=e.created_at,
    )


@router.get(
    "/documents/{document_id}/timeline",
    response_model=list[AuditEventResponse],
    summary="Get the full audit timeline for a document",
    dependencies=[require_role(UserRole.AUDITOR)],
)
async def get_document_timeline(
    document_id: UUID,
    current_user: CurrentUser,
    audit_repo: Annotated[object, Depends(get_audit_repo)],
    limit: int = 200,
) -> list[AuditEventResponse]:
    events = await audit_repo.get_timeline("document", document_id, limit=limit)  # type: ignore[union-attr]
    return [_to_response(e) for e in events]


@router.post(
    "/events/search",
    response_model=list[AuditEventResponse],
    summary="Search audit events with filters",
    dependencies=[require_role(UserRole.AUDITOR)],
)
async def search_audit_events(
    request: AuditSearchRequest,
    current_user: CurrentUser,
    audit_repo: Annotated[object, Depends(get_audit_repo)],
) -> list[AuditEventResponse]:
    events = await audit_repo.search(
        tenant_id=current_user.tenant_id,
        event_types=request.event_types,
        actor_id=request.actor_id,
        from_dt=request.from_dt,
        to_dt=request.to_dt,
        limit=request.limit,
        offset=request.offset,
    )
    return [_to_response(e) for e in events]
