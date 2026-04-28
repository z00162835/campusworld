"""Phase B PR3: task permission codes + system principal."""

from __future__ import annotations

import pytest

from app.services.task.permissions import (
    SYSTEM_DEFAULT_PERMISSIONS,
    SYSTEM_PRINCIPAL,
    TASK_ADMIN,
    TASK_ASSIGN,
    TASK_CANCEL,
    TASK_CLAIM,
    TASK_CREATE,
    TASK_PERMISSIONS,
    TASK_POOL_ADMIN,
    TASK_PUBLISH,
    TASK_READ,
    TASK_UPDATE,
    TASK_APPROVE,
    Principal,
    register_task_permissions_into_admin,
)


@pytest.mark.unit
def test_task_permission_codes_exhaustive_per_spec():
    expected = {
        "task.create",
        "task.read",
        "task.update",
        "task.publish",
        "task.claim",
        "task.assign",
        "task.approve",
        "task.cancel",
        "task.pool.admin",
        "task.admin",
    }
    assert set(TASK_PERMISSIONS) == expected
    assert {
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
    } == expected


@pytest.mark.unit
def test_system_principal_identity():
    assert SYSTEM_PRINCIPAL.id == 0
    assert SYSTEM_PRINCIPAL.kind == "system"


@pytest.mark.unit
def test_system_principal_default_permissions_match_spec_oq28():
    """SPEC §1.4 末段：system 默认持 task.create / publish / claim / read."""
    assert SYSTEM_DEFAULT_PERMISSIONS == {
        TASK_CREATE,
        TASK_PUBLISH,
        TASK_CLAIM,
        TASK_READ,
    }
    assert SYSTEM_PRINCIPAL.permissions == SYSTEM_DEFAULT_PERMISSIONS


@pytest.mark.unit
def test_system_principal_does_not_default_to_admin_perms():
    for code in (TASK_APPROVE, TASK_POOL_ADMIN, TASK_ADMIN):
        assert not SYSTEM_PRINCIPAL.has_permission(code)


@pytest.mark.unit
def test_principal_has_permission_handles_wildcards():
    p = Principal(id=1, kind="user", permissions=frozenset({"task.*"}))
    assert p.has_permission("task.create")
    assert p.has_permission("task.publish")
    assert not p.has_permission("admin.system")


@pytest.mark.unit
def test_principal_has_permission_handles_full_wildcard():
    p = Principal(id=1, kind="user", permissions=frozenset({"*"}))
    assert p.has_permission("task.create")
    assert p.has_permission("admin.system")


@pytest.mark.unit
def test_register_task_permissions_into_admin_idempotent():
    from app.core.permissions import ROLE_STRING_PERMISSIONS, Role

    register_task_permissions_into_admin()
    register_task_permissions_into_admin()
    perms = ROLE_STRING_PERMISSIONS[Role.ADMIN]
    assert perms.count("task.*") == 1
