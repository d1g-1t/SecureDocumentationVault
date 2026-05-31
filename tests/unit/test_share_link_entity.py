from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.domain.entities.share_link import ShareLink


def _make_link(**kwargs) -> ShareLink:
    defaults = {
        "id": uuid4(),
        "document_id": uuid4(),
        "token_hash": "abc123",
        "created_by": uuid4(),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "max_downloads": 5,
        "download_count": 0,
        "password_hash": None,
        "watermark_on_download": True,
        "revoked_at": None,
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return ShareLink(**defaults)


class TestShareLinkCanDownload:
    def test_valid_link_can_download(self) -> None:
        link = _make_link()
        allowed, _ = link.can_download()
        assert allowed is True

    def test_expired_link_cannot_download(self) -> None:
        link = _make_link(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        allowed, reason = link.can_download()
        assert allowed is False
        assert "expired" in reason.lower() or "revoked" in reason.lower()

    def test_revoked_link_cannot_download(self) -> None:
        link = _make_link(revoked_at=datetime.now(timezone.utc))
        allowed, reason = link.can_download()
        assert allowed is False

    def test_exhausted_downloads_cannot_download(self) -> None:
        link = _make_link(max_downloads=3, download_count=3)
        allowed, reason = link.can_download()
        assert allowed is False
        assert "limit" in reason.lower()

    def test_unlimited_downloads(self) -> None:
        link = _make_link(max_downloads=None, download_count=999)
        allowed, _ = link.can_download()
        assert allowed is True


class TestShareLinkRevoke:
    def test_revoke_sets_revoked_at(self) -> None:
        link = _make_link()
        link.revoke()
        assert link.revoked_at is not None

    def test_is_active_property(self) -> None:
        link = _make_link()
        assert link.is_active is True
        link.revoke()
        assert link.is_active is False

    def test_is_exhausted_property(self) -> None:
        link = _make_link(max_downloads=1, download_count=1)
        assert link.is_exhausted is True

    def test_increment_download(self) -> None:
        link = _make_link(download_count=0)
        link.increment_download()
        assert link.download_count == 1
