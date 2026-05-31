from __future__ import annotations

import pytest

from src.infrastructure.security.rbac import is_at_least, requires_role
from src.domain.value_objects import UserRole


class TestRBACHierarchy:
    @pytest.mark.parametrize(
        "user_role, required_role, expected",
        [
            (UserRole.SUPER_ADMIN, UserRole.ADMIN, True),
            (UserRole.ADMIN, UserRole.ARCHIVIST, True),
            (UserRole.ARCHIVIST, UserRole.AUDITOR, True),
            (UserRole.AUDITOR, UserRole.VIEWER, True),
            (UserRole.VIEWER, UserRole.VIEWER, True),
            (UserRole.VIEWER, UserRole.AUDITOR, False),
            (UserRole.AUDITOR, UserRole.ARCHIVIST, False),
            (UserRole.ARCHIVIST, UserRole.ADMIN, False),
            (UserRole.ADMIN, UserRole.SUPER_ADMIN, False),
        ],
    )
    def test_is_at_least(
        self,
        user_role: UserRole,
        required_role: UserRole,
        expected: bool,
    ) -> None:
        assert is_at_least(user_role.value, required_role) is expected

    def test_super_admin_can_do_everything(self) -> None:
        for role in UserRole:
            assert is_at_least(UserRole.SUPER_ADMIN.value, role) is True

    def test_viewer_can_only_view(self) -> None:
        assert is_at_least(UserRole.VIEWER.value, UserRole.VIEWER) is True
        assert is_at_least(UserRole.VIEWER.value, UserRole.AUDITOR) is False


class TestRequiresRole:
    def test_requires_role_passes_for_sufficient_role(self) -> None:
        check = requires_role(UserRole.ARCHIVIST)
        # Should not raise
        check("ADMIN")

    def test_requires_role_fails_for_insufficient_role(self) -> None:
        check = requires_role(UserRole.ADMIN)
        with pytest.raises(PermissionError):
            check("VIEWER")

    def test_requires_role_unknown_role_raises(self) -> None:
        check = requires_role(UserRole.VIEWER)
        with pytest.raises(PermissionError, match="Unknown role"):
            check("NONEXISTENT")
