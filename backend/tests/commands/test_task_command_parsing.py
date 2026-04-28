"""Phase B PR5: argv parsing + i18n + permission gate tests for task commands.

These avoid the database; full state-machine integration is covered in
``tests/integration/test_task_invariants.py`` and the dual-protocol contract
test ``tests/contracts/test_task_dual_protocol.py``.
"""

from __future__ import annotations

import uuid

import pytest

from app.commands.base import CommandContext
from app.commands.game.task._helpers import (
    derive_idempotency_key,
    parse_argv,
    principal_from_context,
    require_permission,
    resolve_principal_or_error,
    task_error_to_result,
)
from app.services.task.errors import UnauthenticatedActor


def _ctx(*, permissions=None, roles=None, user_id="42") -> CommandContext:
    return CommandContext(
        user_id=user_id,
        username="probe",
        session_id="s",
        permissions=list(permissions or []),
        roles=list(roles or []),
        metadata={"locale": "en-US"},
    )


@pytest.mark.unit
def test_parse_argv_basic_flag_value():
    p = parse_argv(["--title", "hello", "--priority", "high"])
    assert p.positional == []
    assert p.flags == {"title": "hello", "priority": "high"}


@pytest.mark.unit
def test_parse_argv_positional_and_flags():
    p = parse_argv(["123", "--to-pool", "hicampus.cleaning"])
    assert p.positional == ["123"]
    assert p.flags["to-pool"] == "hicampus.cleaning"


@pytest.mark.unit
def test_parse_argv_bool_flags():
    p = parse_argv(["--mine", "--limit", "10"], bool_flags={"mine"})
    assert "mine" in p.bools
    assert p.flags["limit"] == "10"


@pytest.mark.unit
def test_principal_from_context_int_id():
    ctx = _ctx(user_id="1234", permissions=["task.create"], roles=["admin"])
    p = principal_from_context(ctx)
    assert p.id == 1234
    assert p.kind == "user"
    assert "task.create" in p.permissions
    assert "admin" in p.roles


@pytest.mark.unit
def test_principal_from_context_uuid_rejects_with_unauthenticated_actor():
    """Regression: UUID user_id MUST NOT be silently downgraded to a privileged
    ``system`` principal — that would bypass all role checks (P0 security)."""
    ctx = _ctx(user_id=str(uuid.uuid4()))
    with pytest.raises(UnauthenticatedActor):
        principal_from_context(ctx)


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad_user_id",
    ["", None, "guest", "GUEST", "abc", "uuid-12345", "0", "-1"],
)
def test_principal_from_context_invalid_user_id_rejects(bad_user_id):
    ctx = _ctx(user_id=bad_user_id)
    with pytest.raises(UnauthenticatedActor):
        principal_from_context(ctx)


@pytest.mark.unit
def test_resolve_principal_or_error_returns_error_for_uuid():
    ctx = _ctx(user_id=str(uuid.uuid4()))
    actor, err = resolve_principal_or_error(ctx)
    assert actor is None
    assert err is not None
    assert err.success is False
    assert err.error == "commands.task.error.unauthenticated"


@pytest.mark.unit
def test_resolve_principal_or_error_returns_principal_for_int():
    ctx = _ctx(user_id="42")
    actor, err = resolve_principal_or_error(ctx)
    assert err is None
    assert actor is not None
    assert actor.id == 42
    assert actor.kind == "user"


@pytest.mark.unit
def test_derive_idempotency_key_is_deterministic():
    actor = principal_from_context(_ctx(user_id="7"))
    a = derive_idempotency_key(actor=actor, command_name="task.publish",
                                args=["1", "--to-pool", "hicampus.cleaning"],
                                correlation_id="corr-1")
    b = derive_idempotency_key(actor=actor, command_name="task.publish",
                                args=["1", "--to-pool", "hicampus.cleaning"],
                                correlation_id="corr-1")
    assert a == b
    assert len(a) == 32


@pytest.mark.unit
def test_derive_idempotency_key_changes_with_args():
    actor = principal_from_context(_ctx(user_id="7"))
    a = derive_idempotency_key(actor=actor, command_name="task.publish",
                                args=["1"], correlation_id=None)
    b = derive_idempotency_key(actor=actor, command_name="task.publish",
                                args=["2"], correlation_id=None)
    assert a != b


@pytest.mark.unit
def test_require_permission_missing_returns_error_result():
    ctx = _ctx(permissions=[])
    res = require_permission(ctx, "task.create")
    assert res is not None
    assert res.success is False
    assert res.error == "commands.task.error.forbidden"


@pytest.mark.unit
def test_require_permission_explicit_pass():
    ctx = _ctx(permissions=["task.create"])
    assert require_permission(ctx, "task.create") is None


@pytest.mark.unit
def test_require_permission_wildcard_pass():
    ctx = _ctx(permissions=["task.*"])
    assert require_permission(ctx, "task.publish") is None
    assert require_permission(ctx, "task.pool.admin") is None


@pytest.mark.unit
def test_require_permission_global_wildcard_pass():
    ctx = _ctx(permissions=["*"])
    assert require_permission(ctx, "task.create") is None


@pytest.mark.unit
def test_require_permission_admin_wildcard_does_not_cover_task_namespace():
    ctx = _ctx(permissions=["admin.*"])
    res = require_permission(ctx, "task.read")
    assert res is not None
    assert res.error == "commands.task.error.forbidden"


@pytest.mark.unit
def test_task_command_dispatch_unknown_subcommand_returns_error():
    from app.commands.game.task.task_command import TaskCommand

    cmd = TaskCommand()
    res = cmd.execute(_ctx(permissions=["task.*"]), ["bogus", "1"])
    assert res.success is False
    assert res.error == "commands.task.error.invalid_event"


@pytest.mark.unit
def test_task_command_no_args_returns_usage():
    from app.commands.game.task.task_command import TaskCommand

    cmd = TaskCommand()
    res = cmd.execute(_ctx(), [])
    assert res.success is False
    assert res.is_usage is True


@pytest.mark.unit
def test_task_create_without_title_returns_usage():
    from app.commands.game.task.task_command import TaskCommand

    cmd = TaskCommand()
    res = cmd.execute(_ctx(permissions=["task.create"]), ["create"])
    assert res.success is False
    assert res.is_usage is True


@pytest.mark.unit
def test_task_create_without_permission_blocked():
    from app.commands.game.task.task_command import TaskCommand

    cmd = TaskCommand()
    res = cmd.execute(_ctx(permissions=[]), ["create", "--title", "x"])
    assert res.success is False
    assert res.error == "commands.task.error.forbidden"


@pytest.mark.unit
def test_task_pool_subcommand_dispatch_no_args():
    from app.commands.game.task.task_command import TaskCommand

    cmd = TaskCommand()
    res = cmd.execute(_ctx(permissions=["task.read"]), ["pool"])
    assert res.success is False
    assert res.is_usage is True


@pytest.mark.unit
def test_task_pool_create_without_pool_admin_perm_blocked():
    from app.commands.game.task.task_command import TaskCommand

    cmd = TaskCommand()
    res = cmd.execute(
        _ctx(permissions=["task.read"]),
        ["pool", "create", "hicampus.test", "--display-name", "Test"],
    )
    assert res.success is False
    assert res.error == "commands.task.error.forbidden"


# ---------------------------------------------------------------------------
# P0-security: refuse to act on unauthenticated actors at command boundary.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_task_create_with_uuid_user_id_rejected_before_state_machine():
    """A caller carrying a UUID-shaped user_id must be refused at the command
    layer BEFORE any DB / state-machine code runs. Previously such a caller
    was silently re-cast to ``system`` and bypassed all role checks."""
    from app.commands.game.task.task_command import TaskCommand

    cmd = TaskCommand()
    res = cmd.execute(
        _ctx(user_id=str(uuid.uuid4()), permissions=["task.create"]),
        ["create", "--title", "x"],
    )
    assert res.success is False
    assert res.error == "commands.task.error.unauthenticated"


@pytest.mark.unit
def test_task_list_with_uuid_user_id_rejected():
    from app.commands.game.task.task_command import TaskCommand

    cmd = TaskCommand()
    res = cmd.execute(
        _ctx(user_id=str(uuid.uuid4()), permissions=["task.read"]),
        ["list"],
    )
    assert res.success is False
    assert res.error == "commands.task.error.unauthenticated"


@pytest.mark.unit
def test_task_show_with_uuid_user_id_rejected():
    from app.commands.game.task.task_command import TaskCommand

    cmd = TaskCommand()
    res = cmd.execute(
        _ctx(user_id=str(uuid.uuid4()), permissions=["task.read"]),
        ["show", "1"],
    )
    assert res.success is False
    assert res.error == "commands.task.error.unauthenticated"


@pytest.mark.unit
def test_task_claim_with_guest_user_id_rejected():
    from app.commands.game.task.task_command import TaskCommand

    cmd = TaskCommand()
    res = cmd.execute(
        _ctx(user_id="guest", permissions=["task.claim"]),
        ["claim", "1"],
    )
    assert res.success is False
    assert res.error == "commands.task.error.unauthenticated"


@pytest.mark.unit
def test_task_publish_with_empty_user_id_rejected():
    from app.commands.game.task.task_command import TaskCommand

    cmd = TaskCommand()
    res = cmd.execute(
        _ctx(user_id="", permissions=["task.publish"]),
        ["publish", "1", "--to-pool", "hicampus.cleaning"],
    )
    assert res.success is False
    assert res.error == "commands.task.error.unauthenticated"


@pytest.mark.unit
def test_task_error_to_result_fallback_code_is_commands_task_error_generic():
    from app.services.task.errors import TaskSystemError

    class NoI18nError(TaskSystemError):
        i18n_key = None  # intentionally broken subclass for fallback path

    res = task_error_to_result(_ctx(), NoI18nError("boom"))
    assert res.success is False
    assert res.error == "commands.task.error.generic"
