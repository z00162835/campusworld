"""Tests for ``find`` (Evennia-style) and ``describe`` read-only graph commands.

The commands use simple SQLAlchemy queries on ``Node`` / ``Relationship``.
For unit coverage we drive them against a lightweight fake session that
mimics just the query API surface we rely on — this keeps the tests
hermetic (no PostgreSQL) while still exercising the argument parsing,
error branches, and output shaping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Sequence

import pytest

from app.commands.base import CommandContext
from app.commands.graph_inspect_commands import (
    DescribeCommand,
    FindCommand,
    _parse_describe_args,
    _parse_find_args,
)


# ---------------------------- fixtures / fakes ----------------------------


@dataclass
class _FakeNode:
    id: int
    type_code: str
    name: str
    description: Optional[str] = None
    location_id: Optional[int] = None
    home_id: Optional[int] = None
    attributes: dict = field(default_factory=dict)
    is_active: bool = True


@dataclass
class _FakeRel:
    id: int
    type_code: str
    source_id: int
    target_id: int
    target_role: Optional[str] = None
    is_active: bool = True


class _FakeQuery:
    """Minimal SQLAlchemy query surrogate.

    Supports the subset used by graph_inspect_commands:
    ``filter`` chained calls, ``count``, ``limit``, ``order_by``, ``all``,
    and ``first``. Actual filtering is delegated to a callback the test
    installs at session construction time so we can precisely control what
    each command "sees".
    """

    def __init__(self, rows: Sequence[Any], limiter: int = 10_000):
        self._rows = list(rows)
        self._limit = limiter
        self.filter_calls: List[tuple] = []

    def filter(self, *args, **_kwargs) -> "_FakeQuery":
        self.filter_calls.append(args)
        return self

    def order_by(self, *_args, **_kwargs) -> "_FakeQuery":
        return self

    def limit(self, n: int) -> "_FakeQuery":
        self._limit = int(n)
        return self

    def count(self) -> int:
        return len(self._rows)

    def all(self) -> List[Any]:
        return list(self._rows[: self._limit])

    def first(self) -> Optional[Any]:
        return self._rows[0] if self._rows else None


class _FakeSession:
    """Delegates ``.query(model)`` to a per-model rows lookup.

    The production helpers call ``session.query(Node)`` or
    ``session.query(Relationship)``; here we route by simple class name.
    """

    def __init__(
        self,
        *,
        nodes: Sequence[_FakeNode] = (),
        rels: Sequence[_FakeRel] = (),
        node_lookup: Optional[Callable[[Sequence[_FakeNode]], Sequence[_FakeNode]]] = None,
    ):
        self._nodes = list(nodes)
        self._rels = list(rels)
        self._node_lookup = node_lookup
        self.last_node_query: Optional[_FakeQuery] = None

    def query(self, model):
        name = getattr(model, "__name__", str(model))
        if name == "Node":
            rows = self._node_lookup(self._nodes) if self._node_lookup else self._nodes
            q = _FakeQuery(rows)
            self.last_node_query = q
            return q
        if name == "Relationship":
            return _FakeQuery(self._rels)
        return _FakeQuery([])


def _ctx(session=None) -> CommandContext:
    return CommandContext(
        user_id="u1",
        username="tester",
        session_id="s1",
        permissions=[],
        roles=[],
        db_session=session,
    )


# --------------------------- _parse_find_args ---------------------------


@pytest.mark.unit
def test_parse_find_args_requires_query_or_type():
    p = _parse_find_args([])
    assert p.error and "requires" in p.error


@pytest.mark.unit
def test_parse_find_args_query_only():
    p = _parse_find_args(["广场"])
    assert p.error is None
    assert p.query == "广场"
    assert p.type_code is None
    assert p.limit == 12


@pytest.mark.unit
def test_parse_find_args_type_and_limit():
    p = _parse_find_args(["hicampus", "--type", "world_entrance", "--limit", "5"])
    assert p.error is None
    assert p.query == "hicampus"
    assert p.type_code == "world_entrance"
    assert p.limit == 5


@pytest.mark.unit
def test_parse_find_args_dbref_shortcut():
    p = _parse_find_args(["#42"])
    assert p.error is None
    assert p.node_id == 42
    assert p.query is None


@pytest.mark.unit
def test_parse_find_args_dbref_rejects_extra_args():
    p = _parse_find_args(["#42", "other"])
    assert p.error and "extra arguments" in p.error


@pytest.mark.unit
def test_parse_find_args_account_shortcut():
    p = _parse_find_args(["*admin"])
    assert p.error is None
    assert p.account_name == "admin"
    # auto-narrows type to account.
    assert p.type_code == "account"
    assert p.query is None


@pytest.mark.unit
def test_parse_find_args_account_respects_explicit_type():
    p = _parse_find_args(["*admin", "--type", "character"])
    assert p.error is None
    assert p.account_name == "admin"
    assert p.type_code == "character"


@pytest.mark.unit
def test_parse_find_args_exact_and_startswith_exclusive():
    p = _parse_find_args(["x", "--exact", "--startswith"])
    assert p.error and "mutually exclusive" in p.error


@pytest.mark.unit
def test_parse_find_args_in_location():
    p = _parse_find_args(["--type", "room", "--in", "1"])
    assert p.error is None
    assert p.type_code == "room"
    assert p.in_location == 1
    assert p.query is None


@pytest.mark.unit
def test_parse_find_args_in_location_rejects_non_integer():
    p = _parse_find_args(["x", "--in", "abc"])
    assert p.error and "--in" in p.error


@pytest.mark.unit
def test_parse_find_args_rejects_unknown_flag():
    p = _parse_find_args(["x", "--nope"])
    assert p.error and "--nope" in p.error


@pytest.mark.unit
def test_parse_find_args_requires_limit_value():
    p = _parse_find_args(["x", "--limit"])
    assert p.error and "--limit" in p.error


@pytest.mark.unit
def test_parse_find_args_rejects_non_integer_limit():
    p = _parse_find_args(["x", "--limit", "abc"])
    assert p.error and "abc" in p.error


@pytest.mark.unit
def test_parse_find_args_caps_limit():
    p = _parse_find_args(["x", "--limit", "999"])
    assert p.error is None
    assert p.limit == 50  # capped at _MAX_LIMIT


# -------------------- v3 migration & flag-surface locks -------------------
# See docs/command/SPEC/features/F01_FIND_COMMAND.md §3 for the migration
# table; these tests regression-lock each row so v2->v3 rename cannot drift.


@pytest.mark.unit
def test_parse_rejects_legacy_long_location_flag():
    p = _parse_find_args(["foo", "--location", "35"])
    assert p.error is not None
    assert "--location" in p.error
    assert "--in" in p.error or "-loc" in p.error


@pytest.mark.unit
def test_parse_short_loc_is_in_location():
    p = _parse_find_args(["foo", "-loc", "35"])
    assert p.error is None
    assert p.in_location == 35


@pytest.mark.unit
def test_parse_short_l_is_limit():
    p = _parse_find_args(["foo", "-l", "7"])
    assert p.error is None
    assert p.limit == 7


@pytest.mark.unit
def test_parse_short_n_is_name_not_limit():
    p = _parse_find_args(["-n", "Atrium"])
    assert p.error is None
    assert p.name == "Atrium"
    assert p.limit == 12  # v3: -n must NOT be treated as --limit anymore


@pytest.mark.unit
def test_parse_describe_flag():
    p = _parse_find_args(["-des", "multi-purpose"])
    assert p.error is None
    assert p.describe == "multi-purpose"


@pytest.mark.unit
def test_parse_describe_long_flag():
    p = _parse_find_args(["--describe", "atrium"])
    assert p.error is None
    assert p.describe == "atrium"


@pytest.mark.unit
def test_parse_name_long_flag():
    p = _parse_find_args(["--name", "Atrium"])
    assert p.error is None
    assert p.name == "Atrium"


@pytest.mark.unit
def test_parse_all_flag_short():
    p = _parse_find_args(["-t", "room", "-a"])
    assert p.error is None
    assert p.all is True


@pytest.mark.unit
def test_parse_all_flag_long():
    p = _parse_find_args(["-t", "room", "--all"])
    assert p.error is None
    assert p.all is True


@pytest.mark.unit
def test_parse_positional_and_name_mutually_exclusive():
    p = _parse_find_args(["hello", "-n", "world"])
    assert p.error is not None
    assert "mutually exclusive" in p.error.lower()


@pytest.mark.unit
def test_parse_positional_and_describe_mutually_exclusive():
    p = _parse_find_args(["hello", "-des", "world"])
    assert p.error is not None
    assert "mutually exclusive" in p.error.lower()


@pytest.mark.unit
def test_parse_combined_spec_example():
    # F01 §7 Example 4: find -n "Name" -t "Room" -des "this is a room" -loc 35
    p = _parse_find_args([
        "-n", "Name", "-t", "Room", "-des", "this is a room", "-loc", "35",
    ])
    assert p.error is None
    assert p.name == "Name"
    assert p.describe == "this is a room"
    assert p.type_code == "Room"
    assert p.in_location == 35


@pytest.mark.unit
def test_parse_name_and_describe_together():
    p = _parse_find_args(["-n", "foo", "-des", "bar"])
    assert p.error is None
    assert p.name == "foo"
    assert p.describe == "bar"


# ------------------------------- find -----------------------------------


@pytest.mark.unit
def test_find_primary_name_and_aliases():
    cmd = FindCommand()
    assert cmd.name == "find"
    # Evennia-style aliases we support.
    for alias in ("@find", "locate"):
        assert alias in cmd.aliases
    # Legacy `graph_find` is fully removed.
    assert "graph_find" not in cmd.aliases


@pytest.mark.unit
def test_graph_find_absent_from_registry_after_initialize():
    """Registry-level regression lock: `graph_find` must not resolve at all.

    Even if someone accidentally re-adds it as an alias, the primary
    slot and the alias index should both come back empty.
    """

    from app.commands.init_commands import initialize_commands
    from app.commands.registry import command_registry

    initialize_commands()
    assert command_registry.get_command("graph_find") is None
    # `find` is what callers should land on instead.
    find_cmd = command_registry.get_command("find")
    assert find_cmd is not None and find_cmd.name == "find"


@pytest.mark.unit
def test_find_requires_db_session():
    cmd = FindCommand()
    res = cmd.execute(_ctx(session=None), ["x"])
    assert not res.success
    assert "DB session" in (res.message or res.error or "")


@pytest.mark.unit
def test_find_returns_no_results_message():
    sess = _FakeSession(nodes=[])
    res = FindCommand().execute(_ctx(sess), ["unknown"])
    assert res.success
    assert "No active nodes matched" in res.message
    assert res.data["results"] == []
    assert res.data["total"] == 0


@pytest.mark.unit
def test_find_renders_hits_with_brief():
    nodes = [
        _FakeNode(id=10, type_code="room", name="Plaza", description="A sunny plaza."),
        _FakeNode(
            id=11,
            type_code="world_entrance",
            name="hicampus",
            description="Entry to HiCampus world.",
            location_id=1,
        ),
    ]
    sess = _FakeSession(nodes=nodes)
    res = FindCommand().execute(_ctx(sess), ["hicampus"])
    assert res.success
    assert "Found 2 node(s)" in res.message
    assert "[10] room: Plaza" in res.message
    assert "[11] world_entrance: hicampus" in res.message
    assert "A sunny plaza." in res.message
    assert res.data["total"] == 2
    assert {d["id"] for d in res.data["results"]} == {10, 11}


@pytest.mark.unit
def test_find_by_dbref_returns_single_node():
    target = _FakeNode(id=42, type_code="room", name="Atrium", description="Glassy.")
    sess = _FakeSession(nodes=[target])
    res = FindCommand().execute(_ctx(sess), ["#42"])
    assert res.success
    assert "Found 1 node(s)" in res.message
    assert "[42] room: Atrium" in res.message
    assert res.data["total"] == 1
    assert res.data["results"][0]["id"] == 42


@pytest.mark.unit
def test_find_by_dbref_not_found():
    sess = _FakeSession(nodes=[])
    res = FindCommand().execute(_ctx(sess), ["#999"])
    assert res.success
    assert "No active node for id=999" in res.message
    assert res.data["total"] == 0


@pytest.mark.unit
def test_find_account_shortcut_renders_header():
    nodes = [_FakeNode(id=7, type_code="account", name="admin")]
    sess = _FakeSession(nodes=nodes)
    res = FindCommand().execute(_ctx(sess), ["*admin"])
    assert res.success, res.message or res.error
    assert "account='admin'" in res.message
    assert "type='account'" in res.message
    assert "[7] account: admin" in res.message


# -------------------------------- describe -------------------------------


@pytest.mark.unit
def test_describe_aliases_match_evennia_examine():
    cmd = DescribeCommand()
    assert cmd.name == "describe"
    for alias in ("examine", "ex"):
        assert alias in cmd.aliases


@pytest.mark.unit
def test_describe_requires_argument():
    sess = _FakeSession()
    res = DescribeCommand().execute(_ctx(sess), [])
    assert not res.success
    assert "describe" in (res.message or res.error or "")


@pytest.mark.unit
def test_describe_not_found():
    sess = _FakeSession(nodes=[])
    res = DescribeCommand().execute(_ctx(sess), ["ghost"])
    assert not res.success
    assert "no active node" in (res.message or res.error or "")


@pytest.mark.unit
def test_describe_accepts_dbref_syntax():
    target = _FakeNode(
        id=42,
        type_code="room",
        name="Atrium",
        description="Glass-roofed atrium.",
        location_id=1,
    )
    sess = _FakeSession(nodes=[target])
    res = DescribeCommand().execute(_ctx(sess), ["#42"])
    assert res.success, res.message or res.error
    assert "[42] room: Atrium" in res.message


@pytest.mark.unit
def test_describe_renders_node_with_attrs_and_edges():
    target = _FakeNode(
        id=42,
        type_code="room",
        name="Atrium",
        description="Glass-roofed atrium.",
        location_id=1,
        attributes={"world_id": "hicampus", "size": "m"},
    )
    other = _FakeNode(id=43, type_code="room", name="Plaza")
    rel = _FakeRel(id=1, type_code="connects_to", source_id=42, target_id=43, target_role="north")

    # First Node query -> list of candidate rows (describe tries .first()).
    # Subsequent queries -> Relationship (edges) and target Node.
    call_count = {"nodes": 0}

    def node_lookup(all_nodes):
        call_count["nodes"] += 1
        if call_count["nodes"] == 1:
            # primary resolve by id/name → return the target
            return [target]
        # edge-target resolve
        return [other]

    sess = _FakeSession(nodes=[target, other], rels=[rel], node_lookup=node_lookup)
    res = DescribeCommand().execute(_ctx(sess), ["42"])
    assert res.success, res.message or res.error
    assert "[42] room: Atrium" in res.message
    assert "Glass-roofed atrium." in res.message
    assert "location_id: 1" in res.message
    assert "attributes (preview)" in res.message
    assert "world_id: hicampus" in res.message
    assert "-[connects_to role=north]-> [43] room: Plaza" in res.message
    assert res.data["id"] == 42


# ------------------- v3 behaviour: query builder & renderer -------------------
# See F01 §4 (AND composition), §5 (--all safety ceiling), §6 (data contract),
# §8 (short-query WARN). These tests do not simulate real SQL; they verify
# that every new flag reaches the SQL pipeline (via filter-call counting) and
# that output shape matches the SPEC.


@pytest.mark.unit
def test_find_query_descriptor_carries_v3_fields():
    session = _FakeSession(nodes=[_FakeNode(1, "room", "Atrium", description="x")])
    res = FindCommand().execute(
        _ctx(session), ["-n", "Atr", "-t", "room", "-des", "x", "-loc", "35"]
    )
    assert res.success, res.message
    q = res.data["query"]
    assert q["name"] == "Atr"
    assert q["describe"] == "x"
    assert q["type_code"] == "room"
    assert q["in_location"] == 35
    assert q["all"] is False
    assert q["limit"] == 12


@pytest.mark.unit
def test_find_name_flag_adds_predicate_to_sql_pipeline():
    session = _FakeSession(nodes=[_FakeNode(1, "room", "Atrium", description="x")])
    FindCommand().execute(_ctx(session), ["-n", "Atrium"])
    fq = session.last_node_query
    assert fq is not None
    # is_active + name => >= 2 filter invocations. v2 positional would have
    # produced only (is_active, name/description OR) => also 2; so the
    # real lock is downstream (descriptor, see above). Keep this as a
    # smoke check that the pipeline is still wired.
    assert len(fq.filter_calls) >= 2


@pytest.mark.unit
def test_find_name_and_describe_produce_two_separate_filter_calls():
    session = _FakeSession(nodes=[_FakeNode(1, "room", "Atrium", description="hall")])
    FindCommand().execute(_ctx(session), ["-n", "Atrium", "-des", "hall"])
    fq = session.last_node_query
    assert fq is not None
    # AND composition: is_active + name + description = 3 filter calls.
    # Under v2 positional this would be 2 (is_active + OR clause).
    assert len(fq.filter_calls) >= 3


@pytest.mark.unit
def test_find_all_bypasses_limit(monkeypatch):
    """--all must ignore --limit and cap at the settings hard_max_limit."""
    import app.commands.graph_inspect_commands as mod
    from app.core.settings import FindCommandConfig

    def _fake_cfg():
        return FindCommandConfig(
            hard_max_limit=3, min_trgm_chars=1, explain_on_all_over=1_000_000
        )

    monkeypatch.setattr(mod, "_find_cfg", _fake_cfg)

    session = _FakeSession(
        nodes=[_FakeNode(i, "room", f"r{i}", description="hall") for i in range(1, 7)]
    )
    res = FindCommand().execute(_ctx(session), ["-t", "room", "-a"])
    assert res.success, res.message
    assert len(res.data["results"]) == 3
    assert res.data["total"] == 6
    assert res.data["next_offset"] == 3
    assert "truncated" in res.message.lower()


@pytest.mark.unit
def test_find_all_under_hard_cap_no_truncation(monkeypatch):
    import app.commands.graph_inspect_commands as mod
    from app.core.settings import FindCommandConfig

    monkeypatch.setattr(
        mod,
        "_find_cfg",
        lambda: FindCommandConfig(hard_max_limit=100, min_trgm_chars=1),
    )

    session = _FakeSession(
        nodes=[_FakeNode(i, "room", f"r{i}", description="x") for i in range(1, 4)]
    )
    res = FindCommand().execute(_ctx(session), ["-t", "room", "-a"])
    assert res.success, res.message
    assert res.data["total"] == 3
    assert res.data["next_offset"] is None
    assert "truncated" not in res.message.lower()


@pytest.mark.unit
def test_find_short_name_value_emits_trgm_warning(caplog):
    """Short ILIKE values degrade pg_trgm; the runtime must WARN."""
    session = _FakeSession(nodes=[_FakeNode(1, "room", "AB", description="x")])
    import logging

    with caplog.at_level(logging.WARNING, logger="app.commands.find"):
        res = FindCommand().execute(_ctx(session), ["-n", "AB"])
    assert res.success
    joined = " ".join(r.getMessage().lower() for r in caplog.records)
    assert "trgm" in joined or "short" in joined


@pytest.mark.unit
def test_find_long_name_value_does_not_emit_trgm_warning(caplog):
    session = _FakeSession(nodes=[_FakeNode(1, "room", "Atrium", description="x")])
    import logging

    with caplog.at_level(logging.WARNING, logger="app.commands.find"):
        FindCommand().execute(_ctx(session), ["-n", "Atrium"])
    joined = " ".join(r.getMessage().lower() for r in caplog.records)
    assert "trgm" not in joined


@pytest.mark.unit
def test_find_data_query_limit_echoes_user_input_even_when_all(monkeypatch):
    """F01 §2: --all silently ignores --limit for SQL but data.query.limit keeps user input for audit."""
    import app.commands.graph_inspect_commands as mod
    from app.core.settings import FindCommandConfig

    monkeypatch.setattr(
        mod,
        "_find_cfg",
        lambda: FindCommandConfig(hard_max_limit=100, min_trgm_chars=1),
    )
    session = _FakeSession(nodes=[_FakeNode(1, "room", "r", description="x")])
    res = FindCommand().execute(_ctx(session), ["-t", "room", "-a", "-l", "7"])
    assert res.data["query"]["limit"] == 7
    assert res.data["query"]["all"] is True


# ---------------------- _parse_describe_args ----------------------
# See docs/command/SPEC/features/CMD_describe.md §Implementation contract.


@pytest.mark.unit
def test_parse_describe_args_identifier_only():
    p = _parse_describe_args(["#42"])
    assert p.error is None
    assert p.identifier == "#42"
    assert p.show_all is False


@pytest.mark.unit
def test_parse_describe_args_bare_token_allowed():
    p = _parse_describe_args(["Atrium"])
    assert p.error is None
    assert p.identifier == "Atrium"
    assert p.show_all is False


@pytest.mark.unit
def test_parse_describe_args_all_flag_short_and_long():
    for tok in ("-a", "--all"):
        p = _parse_describe_args(["#1", tok])
        assert p.error is None
        assert p.identifier == "#1"
        assert p.show_all is True


@pytest.mark.unit
def test_parse_describe_args_flag_order_independent():
    p1 = _parse_describe_args(["-a", "#1"])
    p2 = _parse_describe_args(["#1", "-a"])
    assert p1.error is None and p2.error is None
    assert p1.identifier == p2.identifier == "#1"
    assert p1.show_all is True and p2.show_all is True


@pytest.mark.unit
def test_parse_describe_args_missing_identifier_is_ok_for_parser():
    # Parser returns identifier=None; execute() converts that to usage error.
    p = _parse_describe_args(["-a"])
    assert p.error is None
    assert p.identifier is None
    assert p.show_all is True


@pytest.mark.unit
def test_parse_describe_args_unknown_flag_errors():
    p = _parse_describe_args(["#1", "-z"])
    assert p.error and "unknown flag: -z" in p.error


@pytest.mark.unit
def test_parse_describe_args_unknown_long_flag_errors():
    p = _parse_describe_args(["#1", "--nope"])
    assert p.error and "--nope" in p.error


@pytest.mark.unit
def test_parse_describe_args_multiple_positionals_error():
    p = _parse_describe_args(["#1", "extra"])
    assert p.error and "single" in p.error


# ----------------------- describe -a behaviour -----------------------
# See plan: describe_-a_full_expand — default preview vs full expansion.


def _describe_session_with_target(target, rels, other_nodes):
    """Build a _FakeSession where the first Node query yields `target`,
    any later Node queries (edge target resolution) yield from `other_nodes`
    in insertion order.
    """

    calls = {"n": 0}

    def node_lookup(_all_nodes):
        calls["n"] += 1
        if calls["n"] == 1:
            return [target]
        idx = calls["n"] - 2
        if 0 <= idx < len(other_nodes):
            return [other_nodes[idx]]
        return []

    return _FakeSession(
        nodes=[target, *other_nodes], rels=rels, node_lookup=node_lookup
    )


@pytest.mark.unit
def test_describe_default_preview_truncates_attrs_and_edges():
    long_value = "x" * 200
    attrs = {f"k{i:02d}": f"v{i}" for i in range(14)}
    attrs["k00"] = long_value  # ensure first key has a long value
    target = _FakeNode(
        id=1,
        type_code="room",
        name="Atrium",
        attributes=attrs,
    )
    others = [_FakeNode(id=100 + i, type_code="room", name=f"r{i}") for i in range(10)]
    rels = [
        _FakeRel(id=i, type_code="connects_to", source_id=1, target_id=100 + i)
        for i in range(10)
    ]
    sess = _describe_session_with_target(target, rels, others)

    res = DescribeCommand().execute(_ctx(sess), ["#1"])
    assert res.success, res.message or res.error
    assert "attributes (preview):" in res.message
    # 14 keys total, only 12 shown, surplus footer present
    assert "... (+2 more)" in res.message
    # k11 is the 12th sorted key; still in preview. k12/k13 are not.
    assert "k11: v11" in res.message
    assert "k12:" not in res.message
    # Long value must be trimmed; raw long value must not appear.
    assert long_value not in res.message
    assert "..." in res.message
    # Only 8 edges sampled
    assert res.message.count("-[connects_to") == 8
    assert "out-edges (sample):" in res.message
    # data payload: non-`-a` shape is stable (no attributes / out_edges)
    assert "attributes" not in res.data
    assert "out_edges" not in res.data


@pytest.mark.unit
def test_describe_all_flag_expands_attrs_and_out_edges():
    long_value = "y" * 200
    attrs = {f"k{i:02d}": f"v{i}" for i in range(14)}
    attrs["k00"] = long_value
    target = _FakeNode(
        id=1,
        type_code="room",
        name="Atrium",
        attributes=attrs,
    )
    others = [_FakeNode(id=100 + i, type_code="room", name=f"r{i}") for i in range(10)]
    rels = [
        _FakeRel(id=i, type_code="connects_to", source_id=1, target_id=100 + i)
        for i in range(10)
    ]
    sess = _describe_session_with_target(target, rels, others)

    res = DescribeCommand().execute(_ctx(sess), ["#1", "-a"])
    assert res.success, res.message or res.error
    # Titles switch to full-mode wording.
    assert "attributes:" in res.message
    assert "attributes (preview)" not in res.message
    assert "out-edges:" in res.message
    assert "out-edges (sample)" not in res.message
    # No "+N more" trailer, no "..." truncation.
    assert "+2 more" not in res.message
    assert long_value in res.message  # raw long value appears in full mode
    # All 10 out-edges rendered.
    assert res.message.count("-[connects_to") == 10
    # data payload: `attributes` (full dict) and `out_edges` (10 entries)
    assert res.data["attributes"] == attrs
    assert len(res.data["out_edges"]) == 10
    sample = res.data["out_edges"][0]
    assert set(sample.keys()) == {
        "type_code",
        "target_id",
        "target_type",
        "target_name",
        "target_role",
    }
    assert sample["type_code"] == "connects_to"
    assert sample["target_type"] == "room"


@pytest.mark.unit
def test_describe_all_flag_positional_order_equivalent():
    target = _FakeNode(
        id=1,
        type_code="room",
        name="Atrium",
        attributes={"k": "v"},
    )
    other = _FakeNode(id=2, type_code="room", name="Plaza")
    rel = _FakeRel(id=1, type_code="connects_to", source_id=1, target_id=2)

    def make_session():
        return _describe_session_with_target(target, [rel], [other])

    r1 = DescribeCommand().execute(_ctx(make_session()), ["-a", "#1"])
    r2 = DescribeCommand().execute(_ctx(make_session()), ["#1", "-a"])
    r3 = DescribeCommand().execute(_ctx(make_session()), ["#1", "--all"])
    for r in (r1, r2, r3):
        assert r.success, r.message or r.error
        assert r.data["attributes"] == {"k": "v"}
        assert len(r.data["out_edges"]) == 1
        assert "out-edges:" in r.message


@pytest.mark.unit
def test_describe_unknown_flag_errors():
    sess = _FakeSession(nodes=[])
    res = DescribeCommand().execute(_ctx(sess), ["#1", "-z"])
    assert not res.success
    assert "unknown flag: -z" in (res.message or res.error or "")


@pytest.mark.unit
def test_describe_multiple_positionals_error():
    sess = _FakeSession(nodes=[])
    res = DescribeCommand().execute(_ctx(sess), ["#1", "extra"])
    assert not res.success
    assert "single" in (res.message or res.error or "")


@pytest.mark.unit
def test_describe_all_flag_with_missing_identifier_returns_usage():
    sess = _FakeSession(nodes=[])
    res = DescribeCommand().execute(_ctx(sess), ["-a"])
    assert not res.success
    msg = res.message or res.error or ""
    assert "describe" in msg and "-a" in msg
