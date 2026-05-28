from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from src.application.dto import CurrentUserDTO
from src.application.use_cases.auth_service import AuthService
from src.application.use_cases.document_service import DocumentService
from src.core.security import PasetoService
from src.infrastructure.cache.redis_client import RedisClient
from src.infrastructure.crypto.checksum_service import ChecksumService
from src.infrastructure.crypto.envelope_encryption import EnvelopeEncryptionService
from src.infrastructure.crypto.integrity_chain import IntegrityChainService
from src.infrastructure.database.repositories.audit_repository import AuditRepository
from src.infrastructure.database.repositories.document_repository import DocumentRepository
from src.infrastructure.database.repositories import (
    LegalHoldRepository,
    RetentionRepository,
    ShareRepository,
    SignatureRepository,
)
from src.infrastructure.database.session import AsyncSessionFactory
from src.infrastructure.signatures.cms_verifier import CmsVerifier
from src.infrastructure.storage.minio_storage import MinioStorage

_session_factory = AsyncSessionFactory()
_paseto = PasetoService()
_encryption = EnvelopeEncryptionService()
_checksum = ChecksumService()
_chain = IntegrityChainService()
_storage = MinioStorage()
_redis = RedisClient()
_cms_verifier = CmsVerifier()


def _extract_token(authorization: str = Header(alias="Authorization")) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth header")
    return authorization[7:]


async def get_current_user(token: Annotated[str, Depends(_extract_token)]) -> CurrentUserDTO:
    auth_svc = AuthService(_session_factory, _paseto)
    try:
        return await auth_svc.get_current_user(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc


CurrentUser = Annotated[CurrentUserDTO, Depends(get_current_user)]

def get_document_service() -> DocumentService:
    return DocumentService(
        document_repo=DocumentRepository(_session_factory),
        audit_repo=AuditRepository(_session_factory, _chain),
        legal_hold_repo=LegalHoldRepository(_session_factory),
        retention_repo=RetentionRepository(_session_factory),
        storage=_storage,
        encryption=_encryption,
        checksum_svc=_checksum,
        integrity_chain=_chain,
    )


def get_audit_repo() -> AuditRepository:
    return AuditRepository(_session_factory, _chain)


def get_share_repo() -> ShareRepository:
    return ShareRepository(_session_factory)


def get_signature_repo() -> SignatureRepository:
    return SignatureRepository(_session_factory)


def get_retention_repo() -> RetentionRepository:
    return RetentionRepository(_session_factory)


def get_legal_hold_repo() -> LegalHoldRepository:
    return LegalHoldRepository(_session_factory)


def get_redis() -> RedisClient:
    return _redis


def get_cms_verifier() -> CmsVerifier:
    return _cms_verifier


def get_session_factory() -> AsyncSessionFactory:
    return _session_factory


def get_paseto() -> PasetoService:
    return _paseto


def get_encryption() -> EnvelopeEncryptionService:
    return _encryption


def get_storage() -> MinioStorage:
    return _storage


from src.domain.value_objects import UserRole
from src.infrastructure.security.rbac import requires_role as _requires_role

def get_client_ip(request: Request) -> str | None:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


def get_trace_id(request: Request) -> str | None:
    return request.headers.get("X-Trace-Id")

def require_role(*roles: UserRole):
    check = _requires_role(*roles)

    def dependency(current_user: CurrentUser) -> CurrentUserDTO:
        try:
            check(current_user.role)
        except PermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
            ) from exc
        return current_user

    return Depends(dependency)
