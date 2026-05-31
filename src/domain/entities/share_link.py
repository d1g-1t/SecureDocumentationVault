from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID


@dataclass
class ShareLink:

    id: UUID
    document_id: UUID
    created_by: UUID
    token_hash: str
    expires_at: datetime
    max_downloads: int | None
    download_count: int
    password_hash: str | None
    watermark_on_download: bool
    revoked_at: datetime | None
    created_at: datetime

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        return datetime.now(UTC) < self.expires_at

    @property
    def is_exhausted(self) -> bool:
        if self.max_downloads is None:
            return False
        return self.download_count >= self.max_downloads

    def can_download(self) -> tuple[bool, str]:
        if not self.is_active:
            return False, "Share link has expired or been revoked"
        if self.is_exhausted:
            return False, "Download limit reached"
        return True, ""

    def revoke(self) -> None:
        self.revoked_at = datetime.now(UTC)

    def increment_download(self) -> None:
        self.download_count += 1
