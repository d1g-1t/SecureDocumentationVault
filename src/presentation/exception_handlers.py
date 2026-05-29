from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import ORJSONResponse

from src.core.logging import get_logger
from src.domain.exceptions.domain_exceptions import (
    AccessDeniedError,
    DocumentIntegrityError,
    DocumentNotFoundError,
    DuplicateResourceError,
    LegalHoldViolationError,
    RetentionPolicyViolationError,
    ShareLinkExpiredError,
    ShareLinkExhaustedError,
    SignatureVerificationError,
    StorageObjectMissingError,
    VersionNotFoundError,
)

logger = get_logger(__name__)


def _problem(
    status_code: int,
    title: str,
    detail: str,
    type_: str = "about:blank",
) -> ORJSONResponse:
    return ORJSONResponse(
        status_code=status_code,
        content={
            "type": type_,
            "title": title,
            "status": status_code,
            "detail": detail,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DocumentNotFoundError)
    async def _doc_not_found(request: Request, exc: DocumentNotFoundError) -> ORJSONResponse:
        return _problem(status.HTTP_404_NOT_FOUND, "Document Not Found", str(exc))

    @app.exception_handler(VersionNotFoundError)
    async def _ver_not_found(request: Request, exc: VersionNotFoundError) -> ORJSONResponse:
        return _problem(status.HTTP_404_NOT_FOUND, "Version Not Found", str(exc))

    @app.exception_handler(LegalHoldViolationError)
    async def _legal_hold(request: Request, exc: LegalHoldViolationError) -> ORJSONResponse:
        return _problem(status.HTTP_409_CONFLICT, "Legal Hold Active", str(exc))

    @app.exception_handler(RetentionPolicyViolationError)
    async def _retention(request: Request, exc: RetentionPolicyViolationError) -> ORJSONResponse:
        return _problem(status.HTTP_409_CONFLICT, "Retention Policy Violation", str(exc))

    @app.exception_handler(ShareLinkExpiredError)
    async def _share_expired(request: Request, exc: ShareLinkExpiredError) -> ORJSONResponse:
        return _problem(status.HTTP_410_GONE, "Share Link Expired or Revoked", str(exc))

    @app.exception_handler(ShareLinkExhaustedError)
    async def _share_exhausted(request: Request, exc: ShareLinkExhaustedError) -> ORJSONResponse:
        return _problem(status.HTTP_429_TOO_MANY_REQUESTS, "Download Limit Reached", str(exc))

    @app.exception_handler(SignatureVerificationError)
    async def _sig_error(request: Request, exc: SignatureVerificationError) -> ORJSONResponse:
        return _problem(status.HTTP_422_UNPROCESSABLE_ENTITY, "Signature Verification Failed", str(exc))

    @app.exception_handler(DocumentIntegrityError)
    async def _integrity(request: Request, exc: DocumentIntegrityError) -> ORJSONResponse:
        return _problem(status.HTTP_500_INTERNAL_SERVER_ERROR, "Document Integrity Check Failed", str(exc))

    @app.exception_handler(StorageObjectMissingError)
    async def _storage_missing(request: Request, exc: StorageObjectMissingError) -> ORJSONResponse:
        return _problem(status.HTTP_404_NOT_FOUND, "Storage Object Missing", str(exc))

    @app.exception_handler(AccessDeniedError)
    async def _access_denied(request: Request, exc: AccessDeniedError) -> ORJSONResponse:
        return _problem(status.HTTP_403_FORBIDDEN, "Access Denied", str(exc))

    @app.exception_handler(DuplicateResourceError)
    async def _duplicate(request: Request, exc: DuplicateResourceError) -> ORJSONResponse:
        return _problem(status.HTTP_409_CONFLICT, "Duplicate Resource", str(exc))

    @app.exception_handler(PermissionError)
    async def _permission(request: Request, exc: PermissionError) -> ORJSONResponse:
        return _problem(status.HTTP_403_FORBIDDEN, "Forbidden", str(exc))

    @app.exception_handler(ValueError)
    async def _value_error(request: Request, exc: ValueError) -> ORJSONResponse:
        logger.warning("value_error", error=str(exc))
        return _problem(status.HTTP_400_BAD_REQUEST, "Bad Request", str(exc))

    @app.exception_handler(Exception)
    async def _internal(request: Request, exc: Exception) -> ORJSONResponse:
        logger.error("unhandled_exception", error=str(exc), exc_info=True)
        return _problem(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Internal Server Error",
            "An unexpected error occurred. Please contact support.",
        )
