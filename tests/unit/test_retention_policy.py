from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from src.domain.entities.retention_policy import LegalHold, RetentionPolicy
from src.domain.value_objects import RetentionMode


def _make_policy(**overrides) -> RetentionPolicy:
    defaults = dict(
        id=uuid4(),
        tenant_id=uuid4(),
        name="default",
        retention_mode=RetentionMode.COMPLIANCE,
        retention_days=30,
        allow_delete_after_expiry=False,
        description=None,
        created_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return RetentionPolicy(**defaults)


class TestRetentionPolicy:
    def test_compliance_blocks_delete_before_expiry(self) -> None:
        p = _make_policy(retention_mode=RetentionMode.COMPLIANCE, retention_days=365)
        allowed, reason = p.can_delete(datetime.now(UTC) - timedelta(days=1))
        assert allowed is False
        assert "COMPLIANCE" in reason

    def test_compliance_blocks_delete_even_after_expiry_by_default(self) -> None:
        p = _make_policy(retention_mode=RetentionMode.COMPLIANCE, retention_days=1)
        allowed, _ = p.can_delete(datetime.now(UTC) - timedelta(days=10))
        assert allowed is False

    def test_compliance_allows_delete_after_expiry_when_configured(self) -> None:
        p = _make_policy(
            retention_mode=RetentionMode.COMPLIANCE,
            retention_days=1,
            allow_delete_after_expiry=True,
        )
        allowed, _ = p.can_delete(datetime.now(UTC) - timedelta(days=10))
        assert allowed is True

    def test_governance_allows_delete_before_expiry_if_configured(self) -> None:
        p = _make_policy(
            retention_mode=RetentionMode.GOVERNANCE,
            retention_days=365,
            allow_delete_after_expiry=True,
        )
        allowed, _ = p.can_delete(datetime.now(UTC) - timedelta(days=1))
        assert allowed is True

    def test_governance_blocks_before_expiry_by_default(self) -> None:
        p = _make_policy(retention_mode=RetentionMode.GOVERNANCE, retention_days=365)
        allowed, _ = p.can_delete(datetime.now(UTC) - timedelta(days=1))
        assert allowed is False


class TestLegalHold:
    def test_release_marks_inactive_and_sets_timestamp(self) -> None:
        hold = LegalHold(
            id=uuid4(),
            document_id=uuid4(),
            reason="court order #42",
            placed_by=uuid4(),
            active=True,
            placed_at=datetime.now(UTC),
            released_at=None,
        )
        hold.release()
        assert hold.active is False
        assert hold.released_at is not None
