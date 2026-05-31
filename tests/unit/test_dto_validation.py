from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError


def test_create_share_link_rejects_past_expiry() -> None:
    from src.application.dto import CreateShareLinkRequest

    with pytest.raises(ValidationError):
        CreateShareLinkRequest(expires_at=datetime.now(UTC) - timedelta(hours=1))


def test_create_share_link_accepts_future_expiry() -> None:
    from src.application.dto import CreateShareLinkRequest

    req = CreateShareLinkRequest(
        expires_at=datetime.now(UTC) + timedelta(days=1),
        max_downloads=5,
        watermark_on_download=True,
    )
    assert req.max_downloads == 5
    assert req.watermark_on_download is True


def test_login_request_rejects_short_password() -> None:
    from src.application.dto import LoginRequest

    with pytest.raises(ValidationError):
        LoginRequest(email="user@example.com", password="short")


def test_upload_document_request_requires_title_and_type() -> None:
    from src.application.dto import UploadDocumentRequest

    with pytest.raises(ValidationError):
        UploadDocumentRequest(title="", document_type="contract")

    with pytest.raises(ValidationError):
        UploadDocumentRequest(title="OK", document_type="")


def test_place_legal_hold_requires_meaningful_reason() -> None:
    from src.application.dto import PlaceLegalHoldRequest

    with pytest.raises(ValidationError):
        PlaceLegalHoldRequest(document_id=uuid4(), reason="too short")
