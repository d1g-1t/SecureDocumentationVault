from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import Response

from src.application.dto import CreateShareLinkRequest, ShareLinkResponse
from src.core.logging import get_logger
from src.core.security import PasetoService
from src.domain.entities.share_link import ShareLink
from src.domain.exceptions.domain_exceptions import ShareLinkExpiredError, ShareLinkExhaustedError
from src.domain.value_objects import UserRole
from src.infrastructure.observability.metrics import share_downloads_total, share_links_created_total
from src.infrastructure.security.password_hasher import PasswordHasher
from src.presentation.deps import (
    CurrentUser,
    get_document_service,
    get_paseto,
    get_share_repo,
    require_role,
)

router = APIRouter(prefix="/shares", tags=["share-links"])
logger = get_logger(__name__)
_hasher = PasswordHasher()


def _to_response(share: ShareLink) -> ShareLinkResponse:
    return ShareLinkResponse(
        id=share.id,
        document_id=share.document_id,
        expires_at=share.expires_at,
        max_downloads=share.max_downloads,
        download_count=share.download_count,
        watermark_on_download=share.watermark_on_download,
        revoked_at=share.revoked_at,
        created_at=share.created_at,
        is_active=share.is_active,
    )


@router.post(
    "/{document_id}",
    response_model=ShareLinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a share link for a document",
    dependencies=[require_role(UserRole.ARCHIVIST)],
)
async def create_share_link(
    document_id: UUID,
    request: CreateShareLinkRequest,
    current_user: CurrentUser,
    share_repo: Annotated[object, Depends(get_share_repo)],
) -> ShareLinkResponse:
    raw_token = secrets.token_urlsafe(32)
    token_hash = PasetoService.hash_token(raw_token)

    share = ShareLink(
        id=uuid.uuid4(),
        document_id=document_id,
        created_by=current_user.user_id,
        token_hash=token_hash,
        expires_at=request.expires_at,
        max_downloads=request.max_downloads,
        download_count=0,
        password_hash=_hasher.hash(request.password) if request.password else None,
        watermark_on_download=request.watermark_on_download,
        revoked_at=None,
        created_at=datetime.now(UTC),
    )

    saved = await share_repo.create(share)
    share_links_created_total.labels(tenant_id=str(current_user.tenant_id)).inc()

    response = _to_response(saved)
    logger.info("share_link_created", share_id=str(saved.id), token_preview=raw_token[:8])
    return response


@router.post(
    "/{share_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a share link",
    dependencies=[require_role(UserRole.ARCHIVIST)],
)
async def revoke_share_link(
    share_id: UUID,
    current_user: CurrentUser,
    share_repo: Annotated[object, Depends(get_share_repo)],
) -> None:
    share = await share_repo.get_by_id(share_id)
    if not share:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Share link not found")
    share.revoke()
    await share_repo.update(share)


@router.post(
    "/public/{token}/download",
    summary="Download document via a public share link token (no auth required)",
)
async def public_share_download(
    token: str,
    share_repo: Annotated[object, Depends(get_share_repo)],
    doc_service: Annotated[object, Depends(get_document_service)],
    request: Request,
) -> Response:
    token_hash = PasetoService.hash_token(token)
    share = await share_repo.get_by_token_hash(token_hash)

    if not share:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Share link not found")

    can, reason = share.can_download()
    if not can:
        if "expired" in reason.lower() or "revoked" in reason.lower():
            raise ShareLinkExpiredError()
        raise ShareLinkExhaustedError()

    plain, file_name, mime_type = await doc_service.download_public(
        document_id=share.document_id,
    )

    share.increment_download()
    await share_repo.update(share)

    share_downloads_total.labels(tenant_id="public").inc()

    return Response(
        content=plain,
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
