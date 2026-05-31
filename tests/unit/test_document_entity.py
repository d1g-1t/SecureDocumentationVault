from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.entities.document import Document
from src.domain.value_objects import DocumentStatus


def _make_document(**kwargs) -> Document:
    defaults = {
        "id": uuid4(),
        "tenant_id": uuid4(),
        "title": "Договор №1",
        "document_type": "contract",
        "status": DocumentStatus.ACTIVE,
        "owner_user_id": uuid4(),
        "current_version_id": None,
        "retention_policy_id": None,
        "legal_hold_active": False,
        "tags": [],
        "metadata": {},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return Document(**defaults)


class TestDocumentSoftDelete:
    def test_soft_delete_active_document(self) -> None:
        doc = _make_document()
        doc.soft_delete()
        assert doc.status == DocumentStatus.DELETED

    def test_cannot_delete_already_deleted(self) -> None:
        doc = _make_document(status=DocumentStatus.DELETED)
        allowed, reason = doc.can_be_deleted()
        assert allowed is False
        assert "already deleted" in reason.lower()

    def test_cannot_delete_under_legal_hold(self) -> None:
        doc = _make_document(legal_hold_active=True)
        allowed, reason = doc.can_be_deleted()
        assert allowed is False
        assert "legal hold" in reason.lower()

    def test_privileged_purge_ignores_legal_hold(self) -> None:
        doc = _make_document(legal_hold_active=True)
        allowed, _ = doc.can_be_deleted(privileged_purge=True)
        assert allowed is True


class TestDocumentRestore:
    def test_restore_deleted_document(self) -> None:
        doc = _make_document(status=DocumentStatus.DELETED)
        doc.restore()
        assert doc.status == DocumentStatus.ACTIVE

    def test_restore_active_raises(self) -> None:
        doc = _make_document()
        with pytest.raises(ValueError, match="Only deleted"):
            doc.restore()


class TestDocumentCanBeDeleted:
    def test_active_without_holds_can_delete(self) -> None:
        doc = _make_document()
        allowed, _ = doc.can_be_deleted()
        assert allowed is True

    def test_held_document_cannot_delete(self) -> None:
        doc = _make_document(legal_hold_active=True)
        allowed, _ = doc.can_be_deleted()
        assert allowed is False

    def test_already_deleted_cannot_delete(self) -> None:
        doc = _make_document(status=DocumentStatus.DELETED)
        allowed, _ = doc.can_be_deleted()
        assert allowed is False
