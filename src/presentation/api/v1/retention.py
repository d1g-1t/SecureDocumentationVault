from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from src.application.dto import (
    ApplyRetentionPolicyRequest,
    CreateRetentionPolicyRequest,
    RetentionPolicyResponse,
)
from src.domain.entities.retention_policy import RetentionPolicy
from src.domain.exceptions.domain_exceptions import RetentionPolicyNotFoundError
from src.domain.value_objects import RetentionMode, UserRole
from src.presentation.deps import (
    CurrentUser,
    get_document_service,
    get_retention_repo,
    require_role,
)

router = APIRouter(prefix="/retention", tags=["retention"])


def _to_response(p: RetentionPolicy) -> RetentionPolicyResponse:
    return RetentionPolicyResponse(
        id=p.id,
        tenant_id=p.tenant_id,
        name=p.name,
        retention_mode=p.retention_mode.value,
        retention_days=p.retention_days,
        allow_delete_after_expiry=p.allow_delete_after_expiry,
        description=p.description,
        created_at=p.created_at,
    )


@router.post(
    "/policies",
    response_model=RetentionPolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a retention policy",
    dependencies=[require_role(UserRole.ADMIN)],
)
async def create_policy(
    request: CreateRetentionPolicyRequest,
    current_user: CurrentUser,
    repo: Annotated[object, Depends(get_retention_repo)],
) -> RetentionPolicyResponse:
    policy = RetentionPolicy(
        id=uuid.uuid4(),
        tenant_id=current_user.tenant_id,
        name=request.name,
        retention_mode=RetentionMode(request.retention_mode),
        retention_days=request.retention_days,
        allow_delete_after_expiry=request.allow_delete_after_expiry,
        description=request.description,
        created_at=datetime.now(UTC),
    )
    saved = await repo.create_policy(policy)
    return _to_response(saved)


@router.get(
    "/policies",
    response_model=list[RetentionPolicyResponse],
    summary="List all retention policies for the tenant",
)
async def list_policies(
    current_user: CurrentUser,
    repo: Annotated[object, Depends(get_retention_repo)],
) -> list[RetentionPolicyResponse]:
    policies = await repo.list_policies(current_user.tenant_id)
    return [_to_response(p) for p in policies]


@router.get(
    "/policies/{policy_id}",
    response_model=RetentionPolicyResponse,
    summary="Get a specific retention policy",
)
async def get_policy(
    policy_id: UUID,
    current_user: CurrentUser,
    repo: Annotated[object, Depends(get_retention_repo)],
) -> RetentionPolicyResponse:
    policy = await repo.get_policy(policy_id)
    if not policy:
        raise RetentionPolicyNotFoundError(policy_id)
    return _to_response(policy)


@router.post(
    "/documents/{document_id}/apply",
    response_model=dict,
    summary="Apply a retention policy to a document",
    dependencies=[require_role(UserRole.ADMIN)],
)
async def apply_retention_policy(
    document_id: UUID,
    request: ApplyRetentionPolicyRequest,
    current_user: CurrentUser,
    doc_service: Annotated[object, Depends(get_document_service)],
    repo: Annotated[object, Depends(get_retention_repo)],
) -> dict:
    doc = await doc_service._get_or_raise(document_id, current_user.tenant_id)
    policy = await repo.get_policy(request.retention_policy_id)
    if not policy:
        raise RetentionPolicyNotFoundError(request.retention_policy_id)
    doc.retention_policy_id = request.retention_policy_id
    await doc_service._docs.update(doc)
    return {"status": "policy_applied", "document_id": str(document_id), "policy_id": str(request.retention_policy_id)}
