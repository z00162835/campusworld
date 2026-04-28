"""Tests for ``space`` (SPACE node summary) and shared ``connects_to`` query."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence

import pytest

from app.commands.base import CommandContext
from app.commands.game.look_command import LookCommand
from app.commands.room_connects_to_query import (
    connects_to_exits_from_room,
    connects_to_exit_entries_for_look,
)
from app.commands.space_command import SpaceCommand, parse_space_args


@dataclass
class _N:
    id: int
    type_id: int = 1
    type_code: str = "room"
    name: str = "r"
    description: Optional[str] = None
    location_id: Optional[int] = None
    attributes: dict = field(default_factory=dict)
    is_active: bool = True


@dataclass
class _R:
    id: int
    source_id: int
    target_id: int
    type_code: str = "connects_to"
    attributes: dict = field(default_factory=dict)
    is_active: bool = True


@dataclass
class _NT:
    id: int
    type_code: str
    trait_class: str = "SPACE"


class _Q:
    def __init__(self, rows: List[Any], model: str):
        self._rows = list(rows)
        self._model = model
        self._joined: Optional[str] = None
        self._filters: List[Any] = []

    def join(self, *a: Any) -> "_Q":
        return self

    def filter(self, *a: Any) -> "_Q":
        self._filters.append(a)
        return self

    def order_by(self, *a: Any) -> "_Q":
        return self

    def all(self) -> List[Any]:
        if self._model == "rel_pair":
            out: List[Any] = []
            for t in self._rows:
                if isinstance(t, tuple) and len(t) == 2:
                    out.append(t)
            return out
        return list(self._rows)

    def first(self) -> Optional[Any]:
        return self._rows[0] if self._rows else None


class _Sess:
    def __init__(
        self,
        *,
        nodes: Sequence[_N],
        rels: Sequence[_R],
        ntypes: Sequence[_NT],
    ):
        self._nodes = list(nodes)
        self._rels = list(rels)
        self._nt = {n.id: n for n in ntypes}

    def query(self, *models: Any) -> _Q:  # noqa: ANN001
        model = models[0] if models else object
        name = getattr(model, "__name__", str(model))
        if name == "Node":
            return _Q(self._nodes, "node")
        if name == "Relationship":
            rows: List[Any] = []
            for r in self._rels:
                tgt = self._by_id("node", r.target_id)
                if tgt is not None:
                    rows.append((r, tgt))
            return _Q(rows, "rel_pair")
        if name == "NodeType":
            return _Q(list(self._nt.values()), "ntype")
        return _Q([], "x")

    def _by_id(self, kind: str, i: int) -> Optional[_N]:
        for n in self._nodes:
            if n.id == i:
                return n
        return None


def test_parse_space_args_usage_and_types() -> None:
    p = parse_space_args([])
    assert p.mode == "usage"
    p = parse_space_args(["-t"])
    assert p.mode == "types"
    p = parse_space_args(["-i", "42"])
    assert p.mode == "id" and p.node_id == 42


def test_parse_space_args_bad_combos() -> None:
    p = parse_space_args(["-t", "-i", "1"])
    assert p.error_key == "flags.bad_combo"
    p = parse_space_args(["-i"])
    assert p.error_key == "error.bad_i"
    p = parse_space_args(["-i", "0"])
    assert p.error_key == "error.bad_id"
    p = parse_space_args(["-i", "-3"])
    assert p.error_key == "error.bad_id"


def test_connects_to_shared_look_and_space() -> None:
    """Same underlying relationships yield the same target ids in both views."""
    n1 = _N(10, name="A", type_code="room", attributes={})
    n2 = _N(20, name="B", type_code="room", attributes={})
    r = _R(1, source_id=10, target_id=20, attributes={"direction": "north"})
    s = _Sess(nodes=[n1, n2], rels=[r], ntypes=[])
    for_look = connects_to_exit_entries_for_look(s, 10)  # type: ignore[arg-type]
    for_space = connects_to_exits_from_room(s, 10)  # type: ignore[arg-type]
    assert [e.get("target_display_name") for e in for_look] == [
        e.get("target_display_name") for e in for_space
    ]
    look_cmd = LookCommand()
    le = look_cmd._exit_entries_from_connects_to(s, 10)  # type: ignore[arg-type]
    assert le == for_look


def test_space_execute_room_requires_session() -> None:
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        db_session=None,
    )
    res = SpaceCommand().execute(ctx, ["-i", "1"])
    assert not res.success


def test_space_section4_room_links_includes_direction() -> None:
    cmd = SpaceCommand()
    src = _N(10, type_code="room", name="A")
    dst = _N(20, type_code="room", name="B")
    rel = _R(1, source_id=10, target_id=20, attributes={"direction": "north"})
    sess = _Sess(nodes=[src, dst], rels=[rel], ntypes=[])
    lines, data, mode, fallback = cmd._section4(sess, src, "room", "en-US")  # type: ignore[arg-type]
    assert mode == "room_links"
    assert fallback is False
    assert lines
    assert any("direction" in line for line in lines[:1])
    assert data and data[0]["direction"] == "north"


def test_space_section4_children_direction_none() -> None:
    cmd = SpaceCommand()
    building = _N(100, type_code="building", name="F1", attributes={"package_node_id": "hicampus_f1"})
    floor = _N(101, type_code="building_floor", name="L1", location_id=100)
    sess = _Sess(nodes=[floor], rels=[], ntypes=[])
    lines, data, mode, _fallback = cmd._section4(sess, building, "building", "en-US")  # type: ignore[arg-type]
    assert mode in ("children", "fallback_attr")
    assert lines
    assert data and "direction" in data[0] and data[0]["direction"] is None


@pytest.mark.unit
def test_space_parse_unknown_flag() -> None:
    p = parse_space_args(["-x"])
    assert p.error_key == "error.unknown_flag"
