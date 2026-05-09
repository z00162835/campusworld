"""F13 AICO command surface (argv, helpers)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import uuid

from app.commands.argv_normalize import expand_aico_argv
from app.commands.base import CommandContext
from app.commands.aico_exec import AICO_USAGE_LINE, execute_aico_command, take_last_n_rounds


@pytest.mark.unit
def test_expand_aico_argv_la_and_al():
    assert expand_aico_argv(["-la"]) == ["-l", "-a"]
    assert expand_aico_argv(["-al"]) == ["-l", "-a"]
    assert expand_aico_argv(["-ll"]) == ["-l"]
    assert expand_aico_argv(["-l", "-a"]) == ["-l", "-a"]


@pytest.mark.unit
def test_expand_aico_argv_preserves_multi_char_flags():
    tid = str(uuid.uuid4())
    assert expand_aico_argv(["-his", tid]) == ["-his", tid]
    assert expand_aico_argv(["-cd", tid]) == ["-cd", tid]
    assert expand_aico_argv(["-nd"]) == ["-nd"]
    assert expand_aico_argv(["-i"]) == ["-i"]
    assert expand_aico_argv(["-LA"]) == ["-LA"]


@pytest.mark.unit
def test_take_last_n_rounds_keeps_tail_pair():
    msgs = [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
        {"role": "user", "content": "c"},
        {"role": "assistant", "content": "d"},
    ]
    out = take_last_n_rounds(msgs, 1)
    assert len(out) == 2
    assert out[0]["content"] == "c"
    assert out[1]["content"] == "d"


@pytest.mark.unit
def test_execute_aico_empty_args_usage():
    ctx = CommandContext("1", "u", "s", [], db_session=MagicMock())
    r = execute_aico_command(ctx, [])
    assert not r.success
    assert AICO_USAGE_LINE in (r.message or "")


@pytest.mark.unit
@patch("app.commands.aico_exec.resolve_caller_node_id", return_value=1)
@patch("app.commands.aico_exec._resolve_aico_node")
@patch("app.commands.aico_exec.list_threads_for_owner_agent")
def test_execute_aico_list_limit(mock_list, mock_node, _mock_caller):
    node = MagicMock()
    node.id = 42
    node.attributes = {"decision_mode": "llm", "service_id": "aico"}
    mock_node.return_value = (node, None)
    mock_list.return_value = []

    ctx = CommandContext("1", "u", "s", ["player"], db_session=MagicMock())
    r = execute_aico_command(ctx, ["-l"])
    assert r.success
    mock_list.assert_called_once()
    call_kw = mock_list.call_args.kwargs
    assert call_kw["limit"] == 8


@pytest.mark.unit
@patch("app.commands.aico_exec.resolve_caller_node_id", return_value=1)
@patch("app.commands.aico_exec._resolve_aico_node")
@patch("app.commands.aico_exec.list_threads_for_owner_agent")
def test_execute_aico_list_all(mock_list, mock_node, _mock_caller):
    node = MagicMock()
    node.id = 42
    node.attributes = {"decision_mode": "llm", "service_id": "aico"}
    mock_node.return_value = (node, None)
    mock_list.return_value = []

    ctx = CommandContext("1", "u", "s", ["player"], db_session=MagicMock())
    r = execute_aico_command(ctx, ["-l", "-a"])
    assert r.success
    assert mock_list.call_args.kwargs["limit"] is None


@pytest.mark.unit
@patch("app.commands.aico_exec.resolve_caller_node_id", return_value=1)
@patch("app.commands.aico_exec._resolve_aico_node")
@patch("app.commands.aico_exec.list_threads_for_owner_agent")
def test_execute_aico_list_all_concat_short_opts(mock_list, mock_node, _mock_caller):
    node = MagicMock()
    node.id = 42
    node.attributes = {"decision_mode": "llm", "service_id": "aico"}
    mock_node.return_value = (node, None)
    mock_list.return_value = []

    ctx = CommandContext("1", "u", "s", ["player"], db_session=MagicMock())
    for argv in (["-la"], ["-al"]):
        mock_list.reset_mock()
        r = execute_aico_command(ctx, argv)
        assert r.success
        assert mock_list.call_args.kwargs["limit"] is None
