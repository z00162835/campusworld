"""Task system permission codes and the `system` virtual principal.

SSOT: ``docs/task/SPEC/SPEC.md`` §1.4.

The codes are simple strings to align with the existing
``app.core.permissions`` conventions (string-based with wildcard ``task.*``).
``register_task_permissions_into_admin()`` extends the global ADMIN role to
include the task family without forcing every consumer to be aware of the
new codes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, FrozenSet, Tuple


# Permission codes (SPEC §1.4).
TASK_CREATE: Final[str] = "task.create"
TASK_READ: Final[str] = "task.read"
TASK_UPDATE: Final[str] = "task.update"
TASK_PUBLISH: Final[str] = "task.publish"
TASK_CLAIM: Final[str] = "task.claim"
TASK_ASSIGN: Final[str] = "task.assign"
TASK_APPROVE: Final[str] = "task.approve"
TASK_CANCEL: Final[str] = "task.cancel"
TASK_POOL_ADMIN: Final[str] = "task.pool.admin"
TASK_ADMIN: Final[str] = "task.admin"


TASK_PERMISSIONS: Final[Tuple[str, ...]] = (
    TASK_CREATE,
    TASK_READ,
    TASK_UPDATE,
    TASK_PUBLISH,
    TASK_CLAIM,
    TASK_ASSIGN,
    TASK_APPROVE,
    TASK_CANCEL,
    TASK_POOL_ADMIN,
    TASK_ADMIN,
)


@dataclass(frozen=True)
class Principal:
    """Lightweight actor identity used by the task subsystem.

    Mirrors the ``actor_principal_id`` / ``actor_principal_kind`` columns on
    ``task_state_transitions`` and friends. ``roles`` and ``group_tags`` are
    optional whitelists used by ``evaluate_acl``.
    """

    id: int
    kind: str  # user | agent | group | system
    roles: FrozenSet[str] = frozenset()
    group_tags: FrozenSet[str] = frozenset()
    permissions: FrozenSet[str] = frozenset()

    def has_permission(self, code: str) -> bool:
        if code in self.permissions:
            return True
        if "*" in self.permissions:
            return True
        for p in self.permissions:
            if p.endswith(".*") and code.startswith(p[:-1]):
                return True
        return False


# Default permissions granted to the `system` virtual principal (SPEC §1.4 / OQ-28).
SYSTEM_DEFAULT_PERMISSIONS: Final[FrozenSet[str]] = frozenset(
    {TASK_CREATE, TASK_PUBLISH, TASK_CLAIM, TASK_READ}
)


# Singleton-ish constant exposed for actor injection from automation sources
# (e.g. the consistency_audit worker, sensor-driven task creators in Phase C).
SYSTEM_PRINCIPAL: Final[Principal] = Principal(
    id=0,
    kind="system",
    roles=frozenset(),
    group_tags=frozenset(),
    permissions=SYSTEM_DEFAULT_PERMISSIONS,
)


def register_task_permissions_into_admin() -> None:
    """Extend the global ADMIN role string-permission list with ``task.*``.

    Idempotent. Safe to call multiple times. Imported lazily by callers that
    actually exercise authorization to keep this module free of side-effects
    when only consts are needed.
    """
    from app.core.permissions import ROLE_STRING_PERMISSIONS, Role

    admin_perms = ROLE_STRING_PERMISSIONS.setdefault(Role.ADMIN, [])
    if "task.*" not in admin_perms:
        admin_perms.append("task.*")


__all__ = [
    "TASK_CREATE",
    "TASK_READ",
    "TASK_UPDATE",
    "TASK_PUBLISH",
    "TASK_CLAIM",
    "TASK_ASSIGN",
    "TASK_APPROVE",
    "TASK_CANCEL",
    "TASK_POOL_ADMIN",
    "TASK_ADMIN",
    "TASK_PERMISSIONS",
    "Principal",
    "SYSTEM_DEFAULT_PERMISSIONS",
    "SYSTEM_PRINCIPAL",
    "register_task_permissions_into_admin",
]
