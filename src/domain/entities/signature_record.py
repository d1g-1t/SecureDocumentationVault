from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from src.domain.value_objects import SignatureStatus, SignatureType


@dataclass
class SignatureRecord:

    id: UUID
    document_version_id: UUID
    signature_type: SignatureType
    verification_status: SignatureStatus
    signer_name: str | None
    signer_inn: str | None
    certificate_subject: str | None
    certificate_issuer: str | None
    certificate_serial: str | None
    signing_time: datetime | None
    signature_hash: str | None
    raw_report: dict[str, object]
    verified_at: datetime | None

    @property
    def is_trusted(self) -> bool:
        return self.verification_status == SignatureStatus.VALID
