"""Unit tests for the ``type`` system command.

The command lists active rows from ``node_types`` sorted by ``type_code``
(ASCII a--z, case-insensitive). We avoid a real PostgreSQL by monkeypatching
``app.models.graph.NodeType.get_active_types`` to return synthetic rows; the
command path itself only consumes attribute access (``type_code`` /
``type_name`` / ``description``).

Covered scenarios mirror ``docs/command/SPEC/features/CMD_type.md``:
- default surface caps at 8 rows, sorted by ``type_code`` (not ``type_name``)
- ``description`` in ``data`` is the raw DB value; the text line uses ``-`` for null/blank
- ``-a`` and ``--all`` are equivalent and remove the cap
- unknown flag / positional input short-circuits to error
- empty active set yields the localized empty message + zero-item ``data``
- missing ``db_session`` yields ``error.no_session``
- ``data.items`` order tracks the rendered slice 1:1
- ``en-US`` vs ``zh-CN`` titles differ
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pytest

from app.commands.base import CommandContext
from app.commands.system_commands import TypeCommand, _parse_type_args


# ---------------------------- fixtures / fakes ----------------------------


@dataclass
class _FakeNodeType:
    type_code: str
    type_name: Optional[str] = None
    description: Optional[str] = None
    # ``status`` is not consulted directly: the production code reaches
    # ``NodeType.get_active_types`` which we monkeypatch wholesale.


def _ctx(db_session=object(), locale: str = "en-US") -> CommandContext:
    """Build a context with a non-None db_session sentinel by default.

    The sentinel is fine because ``NodeType.get_active_types`` is patched in
    each test that exercises the success path; it is only the falsy branch
    that we need to drive with ``db_session=None``.
    """
    return CommandContext(
        user_id="u1",
        username="tester",
        session_id="s1",
        permissions=[],
        roles=[],
        db_session=db_session,
        metadata={"locale": locale},
    )


def _patch_active_types(monkeypatch, rows: List[_FakeNodeType]) -> None:
    from app.models.graph import NodeType

    monkeypatch.setattr(
        NodeType, "get_active_types", classmethod(lambda cls, session: list(rows))
    )


def _ten_rows() -> List[_FakeNodeType]:
    """Ten synthetic rows whose ``type_name`` / ``type_code`` letters are out of order.

    Sorted by ``type_code`` ascending the result is ``a1``--``j1`` which maps
    to type_name ``alpha``--``juliet``; the command should
    produce this order regardless of insertion order.
    """
    base = [
        ("c1", "charlie", "third by name"),
        ("a1", "alpha", "first by name"),
        ("d1", "delta", "fourth by name"),
        ("b1", "bravo", "second by name"),
        ("e1", "echo", "fifth by name"),
        ("f1", "foxtrot", "sixth by name"),
        ("g1", "golf", "seventh by name"),
        ("h1", "hotel", "eighth by name"),
        ("i1", "india", "ninth by name"),
        ("j1", "juliet", "tenth by name"),
    ]
    return [_FakeNodeType(code, name, desc) for code, name, desc in base]


# ----------------------------- _parse_type_args ---------------------------


@pytest.mark.unit
def test_parse_type_args_empty_defaults_to_no_show_all():
    p = _parse_type_args([])
    assert p.error is None
    assert p.show_all is False


@pytest.mark.unit
def test_parse_type_args_short_alias_sets_show_all():
    p = _parse_type_args(["-a"])
    assert p.error is None
    assert p.show_all is True


@pytest.mark.unit
def test_parse_type_args_long_alias_sets_show_all():
    p = _parse_type_args(["--all"])
    assert p.error is None
    assert p.show_all is True


@pytest.mark.unit
def test_parse_type_args_unknown_flag_errors():
    p = _parse_type_args(["--bogus"])
    assert p.error is not None
    assert "unknown flag" in p.error
    assert p.show_all is False


@pytest.mark.unit
def test_parse_type_args_rejects_positional():
    p = _parse_type_args(["room"])
    assert p.error is not None
    assert "positional" in p.error


# ----------------------------- TypeCommand.execute -------------------------


@pytest.mark.unit
def test_type_default_caps_at_eight_and_sorts_by_type_code(monkeypatch):
    _patch_active_types(monkeypatch, _ten_rows())
    res = TypeCommand().execute(_ctx(), [])
    assert res.success is True
    assert res.data is not None
    assert res.data["show_all"] is False
    assert res.data["total"] == 10
    items = res.data["items"]
    assert len(items) == TypeCommand.DEFAULT_LIMIT == 8
    rendered_names = [it["type_name"] for it in items]
    assert rendered_names == [
        "alpha",
        "bravo",
        "charlie",
        "delta",
        "echo",
        "foxtrot",
        "golf",
        "hotel",
    ]
    assert "Showing 8 of 10" in res.message
    assert "Pass -a to see all." in res.message


@pytest.mark.unit
def test_type_all_flag_returns_every_active_row(monkeypatch):
    _patch_active_types(monkeypatch, _ten_rows())
    res = TypeCommand().execute(_ctx(), ["-a"])
    assert res.success is True
    assert res.data["show_all"] is True
    assert res.data["total"] == 10
    assert len(res.data["items"]) == 10
    assert "10 active types." in res.message


@pytest.mark.unit
def test_type_long_alias_all_is_equivalent(monkeypatch):
    _patch_active_types(monkeypatch, _ten_rows())
    short = TypeCommand().execute(_ctx(), ["-a"])
    long = TypeCommand().execute(_ctx(), ["--all"])
    assert short.message == long.message
    assert short.data == long.data


@pytest.mark.unit
def test_type_unknown_flag_returns_error(monkeypatch):
    _patch_active_types(monkeypatch, _ten_rows())
    res = TypeCommand().execute(_ctx(), ["--bogus"])
    assert res.success is False
    assert "unknown flag" in res.message


@pytest.mark.unit
def test_type_positional_argument_rejected(monkeypatch):
    _patch_active_types(monkeypatch, _ten_rows())
    res = TypeCommand().execute(_ctx(), ["room"])
    assert res.success is False
    assert "positional" in res.message


@pytest.mark.unit
def test_type_empty_active_set_returns_empty_message(monkeypatch):
    _patch_active_types(monkeypatch, [])
    res = TypeCommand().execute(_ctx(), [])
    assert res.success is True
    assert "No active node types." in res.message
    assert res.data == {"show_all": False, "total": 0, "items": []}


@pytest.mark.unit
def test_type_without_db_session_returns_error():
    res = TypeCommand().execute(_ctx(db_session=None), [])
    assert res.success is False
    assert "Node type list unavailable" in res.message


@pytest.mark.unit
def test_type_data_items_match_rendered_lines_in_order(monkeypatch):
    _patch_active_types(monkeypatch, _ten_rows())
    res = TypeCommand().execute(_ctx(), ["-a"])
    item_codes = [it["type_code"] for it in res.data["items"]]
    rendered_codes: List[str] = []
    for line in res.message.splitlines():
        if line.startswith("[") and "]" in line:
            rendered_codes.append(line[1 : line.index("]")])
    assert rendered_codes == item_codes


@pytest.mark.unit
def test_type_zh_cn_title_uses_localized_text(monkeypatch):
    _patch_active_types(monkeypatch, _ten_rows())
    en = TypeCommand().execute(_ctx(locale="en-US"), [])
    zh = TypeCommand().execute(_ctx(locale="zh-CN"), [])
    assert "Node Types" in en.message
    assert "节点类型" in zh.message
    assert "Showing 8 of 10" in en.message
    assert "已显示前 8 个" in zh.message


@pytest.mark.unit
def test_type_renders_dash_when_description_missing(monkeypatch):
    rows = [
        _FakeNodeType("a1", "alpha", None),
        _FakeNodeType("b1", "bravo", "  "),
    ]
    _patch_active_types(monkeypatch, rows)
    res = TypeCommand().execute(_ctx(), [])
    assert "[a1]  alpha  -  -" in res.message
    assert "[b1]  bravo  -  -" in res.message
    assert res.data["items"][0]["description"] is None
    assert res.data["items"][1]["description"] == "  "


@pytest.mark.unit
def test_type_sorts_by_type_code_not_type_name(monkeypatch):
    """``type_name`` is misleading A/Z; order follows ``type_code``."""

    rows = [
        _FakeNodeType("zebra", "aaa", "x"),
        _FakeNodeType("alpha", "zzz", "y"),
    ]
    _patch_active_types(monkeypatch, rows)
    res = TypeCommand().execute(_ctx(), ["-a"])
    codes = [it["type_code"] for it in res.data["items"]]
    assert codes == ["alpha", "zebra"]
    assert res.message.index("[alpha]") < res.message.index("[zebra]")


@pytest.mark.unit
def test_type_passes_through_db_description_unchanged(monkeypatch):
    _patch_active_types(
        monkeypatch,
        [
            _FakeNodeType("furniture", "家具", "graph seed ontology ensured: furniture"),
        ],
    )
    res = TypeCommand().execute(_ctx(), ["-a"])
    assert "graph seed ontology ensured: furniture" in res.message
    assert res.data["items"][0]["description"] == "graph seed ontology ensured: furniture"
