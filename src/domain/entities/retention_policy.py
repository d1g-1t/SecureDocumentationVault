from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from src.domain.value_objects import RetentionMode


@dataclass
class RetentionPolicy:

    id: UUID
    tenant_id: UUID
    name: str
    retention_mode: RetentionMode
    retention_days: int
    allow_delete_after_expiry: bool
    description: str | None
    created_at: datetime

    def expiry_date(self, document_created_at: datetime) -> datetime:
        return document_created_at + timedelta(days=self.retention_days)

    def can_delete(self, document_created_at: datetime) -> tuple[bool, str]:
        exp = self.expiry_date(document_created_at)
        now = datetime.now(UTC)

        if self.retention_mode == RetentionMode.COMPLIANCE:
            if now < exp:
                return False, f"COMPLIANCE retention: document expires {exp.isoformat()}"
            if not self.allow_delete_after_expiry:
                return False, "Retention policy does not permit deletion after expiry"
        elif self.retention_mode == RetentionMode.GOVERNANCE:
            if now < exp and not self.allow_delete_after_expiry:
                return False, f"GOVERNANCE retention: document expires {exp.isoformat()}"

        return True, ""


@dataclass
class LegalHold:

    id: UUID
    document_id: UUID
    reason: str
    placed_by: UUID
    active: bool
    placed_at: datetime
    released_at: datetime | None

    def release(self) -> None:
        self.active = False
        self.released_at = datetime.now(UTC)
