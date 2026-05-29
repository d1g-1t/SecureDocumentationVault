from __future__ import annotations

from dependency_injector import containers, providers

from src.core.config import get_settings
from src.core.security import PasetoService
from src.infrastructure.cache.redis_client import RedisClient
from src.infrastructure.crypto.checksum_service import ChecksumService
from src.infrastructure.crypto.envelope_encryption import EnvelopeEncryptionService
from src.infrastructure.crypto.integrity_chain import IntegrityChainService
from src.infrastructure.database.repositories.audit_repository import AuditRepository
from src.infrastructure.database.repositories.document_repository import DocumentRepository
from src.infrastructure.database.repositories.legal_hold_repository import LegalHoldRepository
from src.infrastructure.database.repositories.retention_repository import RetentionRepository
from src.infrastructure.database.repositories.share_repository import ShareRepository
from src.infrastructure.database.repositories.signature_repository import SignatureRepository
from src.infrastructure.database.session import AsyncSessionFactory
from src.infrastructure.signatures.cms_verifier import CmsVerifier
from src.infrastructure.storage.minio_storage import MinioStorage


class Container(containers.DeclarativeContainer):

    wiring_config = containers.WiringConfiguration(
        packages=[
            "src.presentation",
        ]
    )

    config = providers.Callable(get_settings)

    session_factory = providers.Singleton(AsyncSessionFactory)

    redis_client = providers.Singleton(RedisClient)

    paseto_service = providers.Singleton(PasetoService)

    minio_storage = providers.Singleton(
        MinioStorage,
        settings=config,
    )

    checksum_service = providers.Singleton(ChecksumService)

    envelope_encryption = providers.Singleton(EnvelopeEncryptionService)

    integrity_chain = providers.Singleton(IntegrityChainService)

    document_repository = providers.Factory(
        DocumentRepository,
        session_factory=session_factory,
    )

    signature_repository = providers.Factory(
        SignatureRepository,
        session_factory=session_factory,
    )

    audit_repository = providers.Factory(
        AuditRepository,
        session_factory=session_factory,
        integrity_chain=integrity_chain,
    )

    share_repository = providers.Factory(
        ShareRepository,
        session_factory=session_factory,
    )

    retention_repository = providers.Factory(
        RetentionRepository,
        session_factory=session_factory,
    )

    legal_hold_repository = providers.Factory(
        LegalHoldRepository,
        session_factory=session_factory,
    )

    cms_verifier = providers.Singleton(CmsVerifier)
