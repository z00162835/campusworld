import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.commands.base import BaseCommand, CommandContext, CommandResult, CommandType
from app.commands.policy import CommandPolicyEvaluator
from app.commands.policy_store import CommandPolicyRepository
from app.commands.registry import CommandRegistry
from app.commands.policy_bootstrap import policy_seed_for


class _DummyCommand(BaseCommand):
    def __init__(self, name: str = "dummy"):
        super().__init__(name=name, description="d", aliases=[], command_type=CommandType.SYSTEM)

    def execute(self, context: CommandContext, args):
        return CommandResult.success_result("ok")


def _policy_row(
    *,
    any_perms=None,
    all_perms=None,
    roles_any=None,
    enabled=True,
):
    m = MagicMock()
    m.enabled = enabled
    m.required_permissions_any = list(any_perms or [])
    m.required_permissions_all = list(all_perms or [])
    m.required_roles_any = list(roles_any or [])
    m.policy_expr = None
    return m


def _ctx(perms, *, db_session=None):
    return CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=perms,
        game_state={},
        db_session=db_session or MagicMock(),
    )


def test_policy_evaluator_denies_without_db_session():
    cmd = _DummyCommand()
    ev = CommandPolicyEvaluator()
    ctx = CommandContext(user_id="1", username="u", session_id="s", permissions=["a.read"], game_state={})
    denied = ev.evaluate(cmd, ctx)
    assert not denied.allowed
    assert denied.reason == "no_db_session"


def test_policy_evaluator_denies_when_no_policy_row():
    cmd = _DummyCommand("my_cmd")
    ev = CommandPolicyEvaluator()
    session = MagicMock()
    with patch.object(CommandPolicyRepository, "get_policy", return_value=None):
        denied = ev.evaluate(cmd, _ctx(["a.read"], db_session=session))
    assert not denied.allowed
    assert denied.reason == "no_policy"


def test_policy_evaluator_denies_when_policy_disabled():
    cmd = _DummyCommand("x")
    ev = CommandPolicyEvaluator()
    session = MagicMock()
    with patch.object(
        CommandPolicyRepository,
        "get_policy",
        return_value=_policy_row(any_perms=["p1"], enabled=False),
    ):
        denied = ev.evaluate(cmd, _ctx(["p1"], db_session=session))
    assert not denied.allowed
    assert denied.reason == "policy_disabled"


def test_policy_evaluator_required_any_and_all_from_db():
    cmd = _DummyCommand()
    ev = CommandPolicyEvaluator()
    session = MagicMock()

    with patch.object(
        CommandPolicyRepository,
        "get_policy",
        return_value=_policy_row(any_perms=["a.read", "a.write"], all_perms=["tenant.x"]),
    ):
        denied = ev.evaluate(cmd, _ctx(["a.read"], db_session=session))
    assert not denied.allowed
    assert denied.reason == "missing_all_permissions"

    with patch.object(
        CommandPolicyRepository,
        "get_policy",
        return_value=_policy_row(any_perms=["a.read", "a.write"], all_perms=["tenant.x"]),
    ):
        allowed = ev.evaluate(cmd, _ctx(["tenant.x", "a.write"], db_session=session))
    assert allowed.allowed


def test_policy_evaluator_policy_expr_allows_and_denies():
    cmd = _DummyCommand("x")
    ev = CommandPolicyEvaluator()
    session = MagicMock()

    row = _policy_row(any_perms=[], all_perms=[])
    row.policy_expr = "perm(admin.*)"

    with patch.object(CommandPolicyRepository, "get_policy", return_value=row):
        denied = ev.evaluate(cmd, _ctx(["user.login"], db_session=session))
    assert not denied.allowed

    with patch.object(CommandPolicyRepository, "get_policy", return_value=row):
        allowed = ev.evaluate(cmd, _ctx(["admin.*"], db_session=session))
    assert allowed.allowed


def test_policy_seed_for_known_and_unknown_commands():
    # Most user-facing commands should be allowed by default.
    assert policy_seed_for("look")["required_permissions_any"] == []
    assert policy_seed_for("world")["required_permissions_any"] == ["admin.world.*"]
    assert policy_seed_for("help") == {
        "required_permissions_any": [],
        "required_permissions_all": [],
        "required_roles_any": [],
    }


def test_registry_uses_db_policy_for_available_commands():
    reg = CommandRegistry()
    c1 = _DummyCommand("c1")
    c2 = _DummyCommand("c2")
    reg.register_command(c1)
    reg.register_command(c2)

    def fake_get(self, name):
        return _policy_row(any_perms=["p1"] if name == "c1" else ["p2"])

    session = MagicMock()
    with patch.object(CommandPolicyRepository, "get_policy", fake_get):
        available = reg.get_available_commands(_ctx(["p2"], db_session=session))
    names = {c.name for c in available}
    assert "c2" in names
    assert "c1" not in names
