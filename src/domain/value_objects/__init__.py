"""Domain value objects — immutable, validated, self-describing."""
from __future__ import annotations

from enum import Enum


class DocumentStatus(str, Enum):
    PROCESSING = "PROCESSING"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"
    CORRUPTED = "CORRUPTED"


class SignatureStatus(str, Enum):
    PENDING = "PENDING"
    VALID = "VALID"
    INVALID = "INVALID"
    UNTRUSTED = "UNTRUSTED"
    EXPIRED_CERT = "EXPIRED_CERT"
    UNKNOWN = "UNKNOWN"


class StorageClass(str, Enum):
    STANDARD = "STANDARD"
    COLD = "COLD"
    GLACIER = "GLACIER"


class RetentionMode(str, Enum):
    GOVERNANCE = "GOVERNANCE"   # Admins can override
    COMPLIANCE = "COMPLIANCE"   # Locked — nobody can delete before expiry


class UserRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    ARCHIVIST = "ARCHIVIST"
    AUDITOR = "AUDITOR"
    VIEWER = "VIEWER"


class SignatureType(str, Enum):
    KEP = "KEP"    # Квалифицированная электронная подпись
    NEP = "NEP"    # Неквалифицированная электронная подпись
    PEP = "PEP"    # Простая электронная подпись
    CMS = "CMS"    # Generic CMS / PKCS#7


class EventType(str, Enum):
    DOCUMENT_CREATED = "DOCUMENT_CREATED"
    DOCUMENT_UPDATED = "DOCUMENT_UPDATED"
    DOCUMENT_DELETED = "DOCUMENT_DELETED"
    DOCUMENT_RESTORED = "DOCUMENT_RESTORED"
    DOCUMENT_DOWNLOADED = "DOCUMENT_DOWNLOADED"
    VERSION_CREATED = "VERSION_CREATED"
    VERSION_DOWNLOADED = "VERSION_DOWNLOADED"
    SIGNATURE_VERIFIED = "SIGNATURE_VERIFIED"
    SHARE_CREATED = "SHARE_CREATED"
    SHARE_REVOKED = "SHARE_REVOKED"
    SHARE_DOWNLOADED = "SHARE_DOWNLOADED"
    LEGAL_HOLD_PLACED = "LEGAL_HOLD_PLACED"
    LEGAL_HOLD_RELEASED = "LEGAL_HOLD_RELEASED"
    RETENTION_APPLIED = "RETENTION_APPLIED"
    KEY_ROTATED = "KEY_ROTATED"
    INTEGRITY_CHECK_FAILED = "INTEGRITY_CHECK_FAILED"
    AUDIT_EXPORTED = "AUDIT_EXPORTED"
    USER_LOGIN = "USER_LOGIN"
    USER_LOGOUT = "USER_LOGOUT"
