from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from fastapi.responses import Response

from src.application.dto import (
    DocumentListResponse,
    DocumentResponse,
    UpdateDocumentRequest,
    UploadDocumentRequest,
    VersionResponse,
)
from src.application.use_cases.document_service import DocumentService
from src.core.config import get_settings
from src.domain.value_objects import UserRole
from src.presentation.deps import (
    CurrentUser,
    get_client_ip,
    get_document_service,
    get_trace_id,
    require_role,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a new document",
    dependencies=[require_role(UserRole.ARCHIVIST)],
)
async def upload_document(
    request: Request,
    title: Annotated[str, Form()],
    document_type: Annotated[str, Form()],
    file: Annotated[UploadFile, File(description="Document file (PDF, DOCX, etc.)")],
    current_user: CurrentUser,
    service: Annotated[DocumentService, Depends(get_document_service)],
    retention_policy_id: Annotated[UUID | None, Form()] = None,
    tags: Annotated[list[str], Form()] = [],
) -> DocumentResponse:
    cfg = get_settings()
    contents = await file.read()

    if len(contents) > cfg.max_upload_size_bytes:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {cfg.max_upload_size_mb}MB",
        )

    upload_req = UploadDocumentRequest(
        title=title,
        document_type=document_type,
        retention_policy_id=retention_policy_id,
        tags=tags,
    )

    return await service.upload_document(
        request=upload_req,
        file_bytes=contents,
        file_name=file.filename or "document",
        mime_type=file.content_type or "application/octet-stream",
        tenant_id=current_user.tenant_id,
        actor_id=current_user.user_id,
        ip_address=get_client_ip(request),
        trace_id=get_trace_id(request),
    )


@router.get(
    "/",
    response_model=DocumentListResponse,
    summary="List documents for the current tenant",
)
async def list_documents(
    current_user: CurrentUser,
    service: Annotated[DocumentService, Depends(get_document_service)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentListResponse:
    from src.domain.value_objects import DocumentStatus
    status_enum = DocumentStatus(status_filter) if status_filter else None
    items, total = await service.list_documents(
        tenant_id=current_user.tenant_id,
        status=status_enum,
        limit=limit,
        offset=offset,
    )
    return DocumentListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document details",
)
async def get_document(
    document_id: UUID,
    current_user: CurrentUser,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentResponse:
    return await service.get_document(document_id, current_user.tenant_id)


@router.post(
    "/{document_id}/download",
    summary="Download current document version (decrypted)",
)
async def download_document(
    document_id: UUID,
    request: Request,
    current_user: CurrentUser,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> Response:
    plain, file_name, mime_type = await service.download_document(
        document_id=document_id,
        tenant_id=current_user.tenant_id,
        actor_id=current_user.user_id,
        ip_address=get_client_ip(request),
        trace_id=get_trace_id(request),
    )
    return Response(
        content=plain,
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a document (checked against legal hold + retention)",
    dependencies=[require_role(UserRole.ARCHIVIST)],
)
async def delete_document(
    document_id: UUID,
    request: Request,
    current_user: CurrentUser,
    service: Annotated[DocumentService, Depends(get_document_service)],
    privileged_purge: Annotated[bool, Query()] = False,
) -> None:
    await service.delete_document(
        document_id=document_id,
        tenant_id=current_user.tenant_id,
        actor_id=current_user.user_id,
        privileged_purge=privileged_purge,
        ip_address=get_client_ip(request),
        trace_id=get_trace_id(request),
    )


@router.post(
    "/{document_id}/restore",
    response_model=DocumentResponse,
    summary="Restore a soft-deleted document",
    dependencies=[require_role(UserRole.ARCHIVIST)],
)
async def restore_document(
    document_id: UUID,
    request: Request,
    current_user: CurrentUser,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentResponse:
    return await service.restore_document(
        document_id=document_id,
        tenant_id=current_user.tenant_id,
        actor_id=current_user.user_id,
        ip_address=get_client_ip(request),
        trace_id=get_trace_id(request),
    )


@router.get(
    "/{document_id}/versions",
    summary="List all versions of a document",
)
async def list_versions(
    document_id: UUID,
    current_user: CurrentUser,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> list[VersionResponse]:
    return await service.list_versions(document_id, current_user.tenant_id)


@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Update document metadata (title, tags)",
    dependencies=[require_role(UserRole.ARCHIVIST)],
)
async def update_document(
    document_id: UUID,
    body: UpdateDocumentRequest,
    request: Request,
    current_user: CurrentUser,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentResponse:
    return await service.update_document(
        document_id=document_id,
        tenant_id=current_user.tenant_id,
        actor_id=current_user.user_id,
        title=body.title,
        tags=body.tags,
        metadata=body.metadata,
        ip_address=get_client_ip(request),
        trace_id=get_trace_id(request),
    )


@router.get(
    "/{document_id}/integrity-report",
    summary="Get integrity chain verification report for a document",
    dependencies=[require_role(UserRole.AUDITOR)],
)
async def get_integrity_report(
    document_id: UUID,
    current_user: CurrentUser,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> dict:
    return await service.verify_integrity(document_id, current_user.tenant_id)
