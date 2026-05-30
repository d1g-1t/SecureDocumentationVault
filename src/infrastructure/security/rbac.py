from __future__ import annotations

from typing import Any

from src.domain.value_objects import UserRole

_ROLE_LEVEL = {
    UserRole.VIEWER: 0,
    UserRole.AUDITOR: 1,
    UserRole.ARCHIVIST: 2,
    UserRole.ADMIN: 3,
    UserRole.SUPER_ADMIN: 4,
}


def requires_role(*allowed_roles: UserRole) -> Any:
    min_level = min(_ROLE_LEVEL[r] for r in allowed_roles)

    def dependency(role: str) -> None:
        try:
            caller_level = _ROLE_LEVEL[UserRole(role)]
        except (ValueError, KeyError) as exc:
            raise PermissionError(f"Unknown role: {role}") from exc
        if caller_level < min_level:
            allowed = ", ".join(r.value for r in allowed_roles)
            raise PermissionError(
                f"Role '{role}' is insufficient. Required: one of [{allowed}]"
            )

    return dependency


def is_at_least(role: str, required: UserRole) -> bool:
    try:
        return _ROLE_LEVEL[UserRole(role)] >= _ROLE_LEVEL[required]
    except (ValueError, KeyError):
        return False
