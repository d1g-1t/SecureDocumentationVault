from __future__ import annotations


class DomainError(Exception):
    pass


class DocumentNotFoundError(DomainError):
    def __init__(self, document_id: object) -> None:
        super().__init__(f"Document {document_id} not found")


class DocumentIntegrityError(DomainError):
    pass


class LegalHoldViolationError(DomainError):

    def __init__(self, document_id: object) -> None:
        super().__init__(f"Document {document_id} is under a legal hold — operation denied")


class RetentionPolicyViolationError(DomainError):

    def __init__(self, detail: str = "Retention policy violation") -> None:
        super().__init__(detail)


class ShareLinkExpiredError(DomainError):
    def __init__(self) -> None:
        super().__init__("Share link has expired or been revoked")


class ShareLinkExhaustedError(DomainError):
    def __init__(self) -> None:
        super().__init__("Share link download limit reached")


class SignatureVerificationError(DomainError):
    pass


class StorageObjectMissingError(DomainError):
    def __init__(self, object_key: str) -> None:
        super().__init__(f"Storage object '{object_key}' not found in the vault")


class AccessDeniedError(DomainError):
    def __init__(self, reason: str = "Access denied") -> None:
        super().__init__(reason)


class VersionNotFoundError(DomainError):
    def __init__(self, version_id: object) -> None:
        super().__init__(f"Document version {version_id} not found")


class RetentionPolicyNotFoundError(DomainError):
    def __init__(self, policy_id: object) -> None:
        super().__init__(f"Retention policy {policy_id} not found")


class TenantNotFoundError(DomainError):
    def __init__(self, tenant_id: object) -> None:
        super().__init__(f"Tenant {tenant_id} not found")


class DuplicateResourceError(DomainError):
    def __init__(self, resource: str) -> None:
        super().__init__(f"{resource} already exists")
