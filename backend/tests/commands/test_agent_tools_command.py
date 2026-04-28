"""Unit tests for ``AgentToolsCommand``.

Covers the dispatcher routes mandated by ``CMD_agent_tools.md``:

1. No-arg list — one row per active ``npc_agent`` rendered in a table.
2. Single-agent query — preserves the legacy ``{"tools":[...]}`` JSON
   message contract while exposing a structured ``data`` mirror.
3. ``add`` / ``del`` — atomic, idempotent edits gated by
   ``admin.agent.tools.manage`` with alias→primary normalization.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from app.commands import agent_commands
from app.commands.agent_commands import (
    AGENT_TOOLS_FORBIDDEN,
    AGENT_TOOLS_MISORDERED,
    AGENT_TOOLS_UNKNOWN_TOOL,
    AgentToolsCommand,
)
from app.commands.base import CommandContext


@pytest.fixture(autouse=True)
def _ensure_commands_loaded():
    """Initialize the global ``command_registry`` once so tool name resolution finds real primaries.

    ``AgentToolsCommand`` resolves user-supplied tool names via
    ``command_registry.get_command``; without ``initialize_commands`` the
    registry is empty and every name would be rejected as unknown.
    """
    from app.commands.init_commands import initialize_commands

    initialize_commands()
    yield


def _ctx(*, db_session: Any = None, permissions: List[str] | None = None, locale: str = "en-US") -> CommandContext:
    return CommandContext(
        user_id="1",
        username="tester",
        session_id="s1",
        permissions=list(permissions or []),
        roles=[],
        db_session=db_session,
        metadata={"locale": locale},
    )


def _mk_agent_node(
    *,
    node_id: int,
    service_id: str,
    name: str,
    tool_allowlist: List[str],
    enabled: bool = True,
    is_active: bool = True,
) -> MagicMock:
    """Build a Node-shaped MagicMock with attributes the command reads."""
    n = MagicMock()
    n.id = node_id
    n.name = name
    n.is_active = is_active
    n.attributes = {
        "service_id": service_id,
        "enabled": enabled,
        "tool_allowlist": list(tool_allowlist),
    }
    return n


@pytest.fixture
def patch_agent_query(monkeypatch):
    """Replace DB-backed agent enumeration and status helpers with stubs."""
    nodes_holder: Dict[str, List[Any]] = {"nodes": []}

    def _fake_query(_session):
        return list(nodes_holder["nodes"])

    def _fake_status(node, _session):
        attrs = dict(node.attributes or {})
        if not node.is_active:
            return "unavailable"
        if attrs.get("enabled") is False:
            return "unavailable"
        return "idle"

    monkeypatch.setattr(agent_commands, "_query_active_npc_agent_nodes", _fake_query)
    monkeypatch.setattr(agent_commands, "derive_agent_status", _fake_status)
    return nodes_holder


@pytest.fixture
def patch_resolve(monkeypatch):
    """Replace ``resolve_npc_agent_by_handle`` with a handle→node table."""
    table: Dict[str, Any] = {}

    def _fake_resolve(_session, handle: str):
        h = (handle or "").strip().lower()
        node = table.get(h)
        if node is None:
            return None, f"unknown agent handle {h!r}"
        return node, None

    monkeypatch.setattr(agent_commands, "resolve_npc_agent_by_handle", _fake_resolve)
    return table


@pytest.fixture
def patch_flag_modified(monkeypatch):
    """``flag_modified`` requires a real mapped instance; substitute a no-op."""
    calls: List[tuple] = []

    def _fake_flag_modified(node, key):
        calls.append((node, key))

    monkeypatch.setattr(agent_commands, "flag_modified", _fake_flag_modified)
    return calls


# ------------------- default list (no args) -------------------


@pytest.mark.unit
def test_agent_tools_default_lists_all_agents_per_row(patch_agent_query, monkeypatch):
    """No-arg form returns one row per active agent and a structured ``data.agents`` payload.

    The effective tool sets are fixed via monkeypatch so the test does not
    depend on per-command policy matrices while still proving row assembly.
    """
    a1 = _mk_agent_node(
        node_id=11, service_id="aico", name="AICO", tool_allowlist=["help", "look"]
    )
    a2 = _mk_agent_node(
        node_id=12, service_id="helper", name="Helper", tool_allowlist=["version"]
    )
    patch_agent_query["nodes"] = [a2, a1]

    def _eff(_session, node, _invoker):
        if node.id == 11:
            return ["help", "look"]
        if node.id == 12:
            return ["version"]
        return []

    def _excl(_node, _eff_list):
        return []

    monkeypatch.setattr(agent_commands, "_effective_tools_for_agent", _eff)
    monkeypatch.setattr(agent_commands, "_excluded_by_policy_on_allowlist", _excl)

    res = AgentToolsCommand().execute(_ctx(db_session=MagicMock()), [])

    assert res.success, res.message
    msg = res.message
    # Header + sorted rows + total footer.
    assert "service_id" in msg and "tools" in msg
    assert msg.find("aico") < msg.find("helper")
    assert "version" in msg
    assert "(total=2)" in msg

    agents = res.data["agents"]
    assert [a["service_id"] for a in agents] == ["aico", "helper"]
    aico_row = agents[0]
    assert aico_row["agent_node_id"] == 11
    assert aico_row["status"] == "idle"
    assert aico_row["tool_count"] == 2
    assert aico_row["tools"] == ["help", "look"]
    assert aico_row["excluded_by_policy"] == []
    assert res.data["total"] == 2


@pytest.mark.unit
def test_no_arg_effective_tools_match_single_agent_output(patch_agent_query, patch_resolve):
    """The no-arg per-row ``tools`` and single-agent ``message`` JSON use the same pipeline."""
    node = _mk_agent_node(
        node_id=99,
        service_id="aico",
        name="AICO",
        tool_allowlist=["help", "look", "version"],
    )
    patch_agent_query["nodes"] = [node]
    patch_resolve["aico"] = node
    session = MagicMock()
    ctx = _ctx(db_session=session)
    r_list = AgentToolsCommand().execute(ctx, [])
    r_one = AgentToolsCommand().execute(ctx, ["aico"])
    assert r_list.success and r_one.success
    t_row = r_list.data["agents"][0]["tools"]
    t_one = json.loads(r_one.message)["tools"]
    assert t_row == t_one
    assert r_list.data["agents"][0]["excluded_by_policy"] == r_one.data["excluded_by_policy"]


@pytest.mark.unit
def test_agent_tools_default_empty_uses_empty_locale(patch_agent_query):
    patch_agent_query["nodes"] = []
    res = AgentToolsCommand().execute(_ctx(db_session=MagicMock()), [])
    assert res.success
    assert "No agents registered." in res.message
    assert res.data == {"agents": [], "total": 0}


@pytest.mark.unit
def test_agent_tools_default_requires_db_session():
    res = AgentToolsCommand().execute(_ctx(db_session=None), [])
    assert not res.success
    assert "database session required" in res.message


@pytest.mark.unit
def test_agent_tools_default_drops_unregistered_aliases(
    patch_agent_query, monkeypatch
):
    """Gibberish in ``tool_allowlist`` is not a registered command — only policy-safe primaries are effective.

    (Unregistered raw tokens do not count toward ``excluded_by_policy`` — they
    are simply never executable.)
    """
    node = _mk_agent_node(
        node_id=21,
        service_id="aico",
        name="AICO",
        tool_allowlist=["help", "definitely-not-a-command"],
    )
    patch_agent_query["nodes"] = [node]

    monkeypatch.setattr(
        agent_commands,
        "_effective_tools_for_agent",
        lambda _s, n, _c: ["help"] if n.id == 21 else [],
    )
    monkeypatch.setattr(
        agent_commands,
        "_excluded_by_policy_on_allowlist",
        lambda n, e: [] if n.id == 21 else [],
    )
    res = AgentToolsCommand().execute(_ctx(db_session=MagicMock()), [])
    assert res.success
    assert res.data["agents"][0]["tools"] == ["help"]
    assert res.data["agents"][0]["excluded_by_policy"] == []


# ------------------- single agent query -------------------


@pytest.mark.unit
def test_agent_tools_misordered_add_gives_i18n_corrective_en():
    """``agent_tools <service_id> add ...`` is parsed as a query for ``service_id``; return hint."""
    res = AgentToolsCommand().execute(
        _ctx(db_session=MagicMock(), locale="en-US"),
        ["aico", "add", "find"],
    )
    assert not res.success
    assert res.error == AGENT_TOOLS_MISORDERED
    assert "agent_tools add" in (res.message or "")
    assert "aico" in (res.message or "")


@pytest.mark.unit
def test_agent_tools_misordered_del_gives_i18n_corrective_zh():
    res = AgentToolsCommand().execute(
        _ctx(db_session=MagicMock(), locale="zh-CN"),
        ["aico", "del", "find"],
    )
    assert not res.success
    assert res.error == AGENT_TOOLS_MISORDERED
    assert "子命令" in (res.message or "") or "须紧跟" in (res.message or "")


@pytest.mark.unit
def test_agent_tools_single_agent_returns_json_message_and_data(patch_resolve, monkeypatch):
    """Single-agent path keeps the JSON ``message`` contract and adds a structured ``data`` mirror."""
    node = _mk_agent_node(
        node_id=42,
        service_id="aico",
        name="AICO",
        tool_allowlist=["help", "look"],
    )
    patch_resolve["aico"] = node

    monkeypatch.setattr(
        agent_commands,
        "command_context_for_npc_agent",
        lambda _s, _n, ctx: ctx,
    )

    class _StubExecutor:
        def list_tool_ids(self, _ctx, allowlist=None):
            return ["agent", "describe", "find", "help", "look"]

    class _StubRouter:
        def __init__(self, allowlist):
            self.allowlist = list(allowlist or [])

        def filter(self, ids):
            allow = set(self.allowlist) if self.allowlist else None
            if allow is None:
                return list(ids)
            return [i for i in ids if i in allow]

    import app.game_engine.agent_runtime.tooling as tooling_mod

    monkeypatch.setattr(tooling_mod, "RegistryToolExecutor", _StubExecutor)
    monkeypatch.setattr(tooling_mod, "ToolRouter", _StubRouter)

    res = AgentToolsCommand().execute(_ctx(db_session=MagicMock()), ["aico"])

    assert res.success
    assert json.loads(res.message) == {"tools": ["help", "look"]}
    assert res.data == {
        "service_id": "aico",
        "agent_node_id": 42,
        "tools": ["help", "look"],
        "excluded_by_policy": [],
    }


@pytest.mark.unit
def test_agent_tools_single_agent_resolve_error_propagates(patch_resolve):
    res = AgentToolsCommand().execute(_ctx(db_session=MagicMock()), ["nope"])
    assert not res.success
    assert "unknown agent handle" in res.message


# ------------------- add / del write paths -------------------


@pytest.mark.unit
def test_agent_tools_add_requires_admin_permission(patch_resolve):
    res = AgentToolsCommand().execute(
        _ctx(db_session=MagicMock(), permissions=[]),
        ["add", "aico", "help"],
    )
    assert not res.success
    assert res.error == AGENT_TOOLS_FORBIDDEN
    assert "Permission denied" in res.message


@pytest.mark.unit
def test_agent_tools_add_requires_db_session():
    res = AgentToolsCommand().execute(
        _ctx(db_session=None, permissions=["admin.agent.tools.manage"]),
        ["add", "aico", "help"],
    )
    assert not res.success
    assert "database session required" in res.message


@pytest.mark.unit
def test_agent_tools_add_appends_and_is_idempotent(patch_resolve, patch_flag_modified):
    node = _mk_agent_node(
        node_id=42, service_id="aico", name="AICO", tool_allowlist=["help"]
    )
    patch_resolve["aico"] = node
    session = MagicMock()

    res = AgentToolsCommand().execute(
        _ctx(db_session=session, permissions=["admin.agent.tools.manage"]),
        ["add", "aico", "help", "look"],
    )

    assert res.success, res.message
    m = res.message or ""
    assert "aico" in m and "look" in m and "help" in m
    assert "add" in m.lower()
    assert res.data["added"] == ["look"]
    assert res.data["unchanged"] == ["help"]
    assert node.attributes["tool_allowlist"] == ["help", "look"]
    assert patch_flag_modified, "flag_modified must run before commit"
    session.commit.assert_called_once()


@pytest.mark.unit
def test_agent_tools_add_normalizes_alias_to_primary(patch_resolve, patch_flag_modified):
    node = _mk_agent_node(
        node_id=42, service_id="aico", name="AICO", tool_allowlist=[]
    )
    patch_resolve["aico"] = node

    res = AgentToolsCommand().execute(
        _ctx(db_session=MagicMock(), permissions=["admin.agent.tools.manage"]),
        ["add", "aico", "ex"],
    )

    assert res.success, res.message
    assert node.attributes["tool_allowlist"] == ["describe"]
    assert res.data["added"] == ["describe"]


@pytest.mark.unit
def test_agent_tools_add_rejects_unknown_tool_without_writing(patch_resolve, patch_flag_modified):
    node = _mk_agent_node(
        node_id=42, service_id="aico", name="AICO", tool_allowlist=["help"]
    )
    patch_resolve["aico"] = node
    session = MagicMock()

    res = AgentToolsCommand().execute(
        _ctx(db_session=session, permissions=["admin.agent.tools.manage"]),
        ["add", "aico", "look", "definitely-not-a-command"],
    )

    assert not res.success
    assert res.error == AGENT_TOOLS_UNKNOWN_TOOL
    assert "definitely-not-a-command" in res.message
    assert node.attributes["tool_allowlist"] == ["help"]
    session.commit.assert_not_called()
    assert not patch_flag_modified


@pytest.mark.unit
def test_agent_tools_add_usage_when_tool_missing(patch_resolve):
    res = AgentToolsCommand().execute(
        _ctx(db_session=MagicMock(), permissions=["admin.agent.tools.manage"]),
        ["add", "aico"],
    )
    assert not res.success
    assert "agent_tools add" in res.message


@pytest.mark.unit
def test_agent_tools_del_removes_and_is_idempotent(patch_resolve, patch_flag_modified):
    node = _mk_agent_node(
        node_id=42, service_id="aico", name="AICO", tool_allowlist=["help", "look"]
    )
    patch_resolve["aico"] = node

    res = AgentToolsCommand().execute(
        _ctx(db_session=MagicMock(), permissions=["admin.agent.tools.manage"]),
        ["del", "aico", "look", "primer"],
    )

    assert res.success, res.message
    m = res.message or ""
    assert "aico" in m and "look" in m and "primer" in m
    assert "del" in m.lower()
    assert res.data["removed"] == ["look"]
    assert res.data["unchanged"] == ["primer"]
    assert node.attributes["tool_allowlist"] == ["help"]


@pytest.mark.unit
def test_agent_tools_del_unknown_tool_rejected(patch_resolve, patch_flag_modified):
    node = _mk_agent_node(
        node_id=42, service_id="aico", name="AICO", tool_allowlist=["help"]
    )
    patch_resolve["aico"] = node

    res = AgentToolsCommand().execute(
        _ctx(db_session=MagicMock(), permissions=["admin.agent.tools.manage"]),
        ["del", "aico", "no-such-tool"],
    )
    assert not res.success
    assert res.error == AGENT_TOOLS_UNKNOWN_TOOL
    assert node.attributes["tool_allowlist"] == ["help"]


@pytest.mark.unit
def test_agent_tools_admin_wildcard_grants_write(patch_resolve, patch_flag_modified):
    node = _mk_agent_node(
        node_id=42, service_id="aico", name="AICO", tool_allowlist=[]
    )
    patch_resolve["aico"] = node

    res = AgentToolsCommand().execute(
        _ctx(db_session=MagicMock(), permissions=["admin.*"]),
        ["add", "aico", "help"],
    )
    assert res.success
    assert node.attributes["tool_allowlist"] == ["help"]
