import sys
from pathlib import Path
from unittest.mock import MagicMock

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.commands.policy_store import CommandPolicyRepository, CommandPolicy


def test_get_policy_returns_none_on_empty_name():
    session = MagicMock()
    repo = CommandPolicyRepository(session)
    assert repo.get_policy("") is None


def test_list_policies_enabled_only_applies_filter():
    session = MagicMock()
    query = session.query.return_value
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = []

    repo = CommandPolicyRepository(session)
    out = repo.list_policies(enabled_only=True)
    assert out == []
    assert session.query.called
    assert query.filter.called


def test_upsert_policy_create_and_update_versioning():
    session = MagicMock()
    repo = CommandPolicyRepository(session)

    # create branch
    repo.get_policy = lambda _name: None
    created = repo.upsert_policy(
        "notice",
        required_permissions_any=["admin.system_notice"],
        enabled=True,
        updated_by="tester",
    )
    assert isinstance(created, CommandPolicy)
    assert created.command_name == "notice"
    assert created.version == 1
    assert created.required_permissions_any == ["admin.system_notice"]

    # update branch
    existing = CommandPolicy(
        command_name="notice",
        required_permissions_any=["old"],
        required_permissions_all=[],
        required_roles_any=[],
        enabled=True,
        scope="global",
        version=3,
    )
    repo.get_policy = lambda _name: existing
    updated = repo.upsert_policy(
        "notice",
        required_permissions_any=["admin.system_notice"],
        required_permissions_all=["tenant.main"],
        enabled=False,
        updated_by="tester2",
    )
    assert updated.version == 4
    assert updated.required_permissions_all == ["tenant.main"]
    assert updated.enabled is False

