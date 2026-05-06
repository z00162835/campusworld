"""F13 §10.5 tick lifecycle NDJSON + assistant body stream (unit)."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.commands.aico_exec import execute_aico_command
from app.ssh.nested_repl.aico_repl import AicoNestedReplDriver
from app.commands.aico_stream import (
    AICO_CLIENT_HINTS,
    emit_assistant_stream_ndjson,
    emit_tick_lifecycle_meta,
)
from app.commands.base import CommandContext
from app.commands.npc_agent_nlp import NPC_AGENT_LLM_FAILURE_USER_MSG, run_npc_agent_nlp_tick
from app.game_engine.agent_runtime.agent_llm_config import invalidate_aico_system_llm_config
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunResult
from app.game_engine.agent_runtime.llm_client import StubLlmClient


def _parse_lines(lines: list[str]) -> list[dict]:
    return [json.loads(line) for line in lines]


@pytest.mark.unit
def test_emit_tick_invalid_client_hint_raises():
    lines: list[str] = []
    with pytest.raises(ValueError):
        emit_tick_lifecycle_meta(lines.append, phase="start", client_hint="nope")


@pytest.mark.unit
def test_emit_assistant_stream_allow_empty_emits_stream_meta_end_only():
    lines: list[str] = []
    tid = uuid.uuid4()
    emit_assistant_stream_ndjson(
        lines.append,
        "",
        thread_id=tid,
        correlation_id="c1",
        allow_empty_body=True,
    )
    evs = _parse_lines(lines)
    assert evs[0]["kind"] == "meta" and evs[0]["scope"] == "stream"
    assert evs[1]["kind"] == "end" and evs[1]["full_text"] == ""
    assert len(evs) == 2


@pytest.mark.unit
def test_aico_client_hints_frozen_set():
    assert AICO_CLIENT_HINTS == frozenset({"running", "finding", "looking", "thinking", "flying"})


@pytest.fixture
def stream_ndjson_mocks(monkeypatch):
    invalidate_aico_system_llm_config()
    mock_cm = MagicMock()
    mock_cm.get_nested.return_value = {}
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.agent_llm_config.get_config",
        lambda: mock_cm,
    )
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.llm_client.http_llm_available",
        lambda _cfg: True,
    )
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.llm_client.build_llm_client_from_service_config",
        lambda _cfg: StubLlmClient(),
    )
    cfg_mock = MagicMock()
    cfg_mock.extra = {}
    cfg_mock.max_tokens = 512
    cfg_mock.model = None
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.agent_llm_config.resolve_agent_llm_config_for_npc_tick",
        lambda *a, **k: cfg_mock,
    )

    mock_worker = MagicMock()
    mock_worker.tool_manifest_text = ""
    mock_worker.tool_schemas = []
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.worker.LlmPdcaAssistantWorker.create",
        lambda *a, **k: mock_worker,
    )
    return mock_worker


@pytest.mark.unit
def test_npc_agent_nlp_stream_success_order(stream_ndjson_mocks, monkeypatch):
    mock_worker = stream_ndjson_mocks
    mock_worker.tick.return_value = FrameworkRunResult(ok=True, message="hello world", final_phase="act")

    lines: list[str] = []
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="sess-1",
        permissions=[],
        metadata={},
    )
    ctx.supports_aico_stream = True
    ctx.stream_emit = lines.append

    session = MagicMock()
    node = MagicMock()
    node.id = 42
    node.attributes = {
        "service_id": "aico",
        "decision_mode": "llm",
        "model_config_ref": "aico",
    }

    res = run_npc_agent_nlp_tick(session, node, ctx, "ping", memory_context=None)
    assert res.ok
    evs = _parse_lines(lines)
    assert evs[0]["scope"] == "tick" and evs[0]["phase"] == "start" and evs[0]["client_hint"] == "running"
    assert evs[1]["scope"] == "stream"
    assert evs[2]["kind"] == "delta"
    assert evs[-2]["kind"] == "end"
    assert evs[-1]["scope"] == "tick" and evs[-1]["phase"] == "complete" and evs[-1]["ok"] is True
    assert evs[-1].get("empty_reply") is False
    assert ctx.metadata.get("_aico_stream_emitted") is True


@pytest.mark.unit
def test_npc_agent_nlp_stream_success_empty_reply(stream_ndjson_mocks, monkeypatch):
    mock_worker = stream_ndjson_mocks
    mock_worker.tick.return_value = FrameworkRunResult(ok=True, message="   ", final_phase="act")

    lines: list[str] = []
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="sess-1",
        permissions=[],
        metadata={},
    )
    ctx.supports_aico_stream = True
    ctx.stream_emit = lines.append

    session = MagicMock()
    node = MagicMock()
    node.id = 42
    node.attributes = {
        "service_id": "aico",
        "decision_mode": "llm",
        "model_config_ref": "aico",
    }

    res = run_npc_agent_nlp_tick(session, node, ctx, "ping", memory_context=None)
    assert res.ok
    evs = _parse_lines(lines)
    assert evs[-1]["empty_reply"] is True
    assert evs[-2]["kind"] == "end" and evs[-2]["full_text"] == ""


@pytest.mark.unit
def test_npc_agent_nlp_stream_tick_failed_emits_error(stream_ndjson_mocks, monkeypatch):
    mock_worker = stream_ndjson_mocks
    mock_worker.tick.return_value = FrameworkRunResult(ok=False, message="bad", final_phase="gate")

    lines: list[str] = []
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="sess-1",
        permissions=[],
        metadata={},
    )
    ctx.supports_aico_stream = True
    ctx.stream_emit = lines.append

    session = MagicMock()
    node = MagicMock()
    node.id = 42
    node.attributes = {
        "service_id": "aico",
        "decision_mode": "llm",
        "model_config_ref": "aico",
    }

    res = run_npc_agent_nlp_tick(session, node, ctx, "ping", memory_context=None)
    assert not res.ok
    evs = _parse_lines(lines)
    assert evs[0]["phase"] == "start"
    assert evs[1]["kind"] == "error" and evs[1]["code"] == "tick_failed"
    assert evs[1]["message"] == "bad"


@pytest.mark.unit
def test_npc_agent_nlp_stream_tick_exception_emits_error(stream_ndjson_mocks, monkeypatch):
    mock_worker = stream_ndjson_mocks
    mock_worker.tick.side_effect = RuntimeError("boom")

    lines: list[str] = []
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="sess-1",
        permissions=[],
        metadata={},
    )
    ctx.supports_aico_stream = True
    ctx.stream_emit = lines.append

    session = MagicMock()
    node = MagicMock()
    node.id = 42
    node.attributes = {
        "service_id": "aico",
        "decision_mode": "llm",
        "model_config_ref": "aico",
    }

    res = run_npc_agent_nlp_tick(session, node, ctx, "ping", memory_context=None)
    assert not res.ok
    evs = _parse_lines(lines)
    assert evs[0]["phase"] == "start"
    assert evs[1]["kind"] == "error" and evs[1]["code"] == "tick_exception"
    assert evs[1]["message"] == NPC_AGENT_LLM_FAILURE_USER_MSG


@pytest.mark.unit
def test_npc_agent_nlp_no_stream_no_side_lines(stream_ndjson_mocks, monkeypatch):
    mock_worker = stream_ndjson_mocks
    mock_worker.tick.return_value = FrameworkRunResult(ok=True, message="hi", final_phase="act")

    lines: list[str] = []
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="sess-1",
        permissions=[],
        metadata={},
    )
    ctx.supports_aico_stream = False
    ctx.stream_emit = lines.append

    session = MagicMock()
    node = MagicMock()
    node.id = 42
    node.attributes = {
        "service_id": "aico",
        "decision_mode": "llm",
        "model_config_ref": "aico",
    }

    run_npc_agent_nlp_tick(session, node, ctx, "ping", memory_context=None)
    assert lines == []
    assert not ctx.metadata.get("_aico_stream_emitted")


@pytest.mark.unit
@patch("app.commands.aico_exec.resolve_caller_node_id", return_value=1)
@patch("app.commands.aico_exec._resolve_aico_node")
def test_aico_interactive_sets_repl_flag_not_ndjson_ephemeral(_mock_node, _mock_caller):
    """Native SSH REPL uses plain progress (aico_progress_emit), not PTY NDJSON (F13 §17.7)."""
    node = MagicMock()
    node.id = 42
    node.attributes = {"decision_mode": "llm", "service_id": "aico"}
    _mock_node.return_value = (node, None)
    sess = MagicMock()
    sess.command_ephemeral = {}
    sess.nested_repl = None
    ctx = CommandContext("1", "u", "s", ["player"], db_session=MagicMock(), session=sess)
    r = execute_aico_command(ctx, ["-i"])
    assert r.success
    assert isinstance(sess.nested_repl, AicoNestedReplDriver)
    assert sess.command_ephemeral.get("supports_aico_stream") is not True


@pytest.mark.unit
@patch("app.commands.aico_stream.random.choice", return_value="running")
def test_npc_agent_nlp_progress_emit_when_no_stream(_mock_choice, stream_ndjson_mocks, monkeypatch):
    mock_worker = stream_ndjson_mocks
    mock_worker.tick.return_value = FrameworkRunResult(ok=True, message="hi", final_phase="act")
    progress_lines: list[str] = []

    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="sess-1",
        permissions=[],
        metadata={},
    )
    ctx.supports_aico_stream = False
    ctx.aico_progress_emit = progress_lines.append

    session = MagicMock()
    node = MagicMock()
    node.id = 42
    node.attributes = {
        "service_id": "aico",
        "decision_mode": "llm",
        "model_config_ref": "aico",
    }

    run_npc_agent_nlp_tick(session, node, ctx, "ping", memory_context=None)
    blob = "".join(progress_lines)
    assert "\r[aico] running…\r\n" in blob
    assert ctx.metadata.get("_aico_stream_emitted") is not True


@pytest.mark.unit
def test_aico_repl_progress_message_uses_frozen_hints():
    from app.commands.aico_stream import AICO_CLIENT_HINTS, aico_repl_progress_message

    for _ in range(30):
        msg = aico_repl_progress_message()
        assert msg.startswith("\r[aico] ")
        assert msg.endswith("…\r\n")
        inner = msg[len("\r[aico] ") : -len("…\r\n")]
        assert inner in AICO_CLIENT_HINTS


@pytest.mark.unit
def test_ssh_handler_failed_stream_shows_complete_then_error():
    from app.commands.base import CommandResult
    from app.protocols.ssh_handler import SSHHandler

    h = SSHHandler()
    r = CommandResult(
        success=False,
        message="bad",
        data={"aico_stream_used": True},
        error="aico_tick_failed",
    )
    out = h._format_command_result(r)
    assert out.startswith("[stream complete]\n")
    assert "Error: bad" in out


@pytest.mark.unit
def test_assistant_nlp_command_result_failure_keeps_stream_flag():
    from app.commands.npc_agent_nlp import assistant_nlp_command_result

    ctx = CommandContext("1", "u", "s", [], metadata={"_aico_stream_emitted": True})
    res = FrameworkRunResult(ok=False, message="oops", final_phase="error")
    cr = assistant_nlp_command_result("aico", res, context=ctx)
    assert cr.success is False
    assert (cr.data or {}).get("aico_stream_used") is True
