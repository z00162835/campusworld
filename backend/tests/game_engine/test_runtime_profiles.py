from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.commands.base import CommandContext
from app.core.log.aico_observability import get_aico_correlation_from_context, get_aico_run_id_from_context, is_aico_full_chain_tick, should_emit_aico_full_chain_logs
from app.game_engine.agent_runtime.aico.profile import AicoRuntimeProfile
from app.game_engine.agent_runtime.agent_tick_context import CallerGraphSnapshot
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunResult
from app.game_engine.agent_runtime.observability import agent_runtime_observability_context, get_agent_runtime_correlation_from_context, get_agent_runtime_run_id_from_context, log_agent_runtime_http_exchange
from app.game_engine.agent_runtime.resolved_tool_surface import ResolvedToolSurface
from app.game_engine.agent_runtime.tool_calling import ToolSchema
from app.game_engine.agent_runtime.profiles import resolve_agent_runtime_profile


@pytest.mark.unit
def test_non_aico_profile_is_noop_for_streaming_and_progress():
    emitted: list[str] = []
    progress: list[str] = []
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        roles=[],
        metadata={},
    )
    ctx.supports_aico_stream = True
    ctx.stream_emit = emitted.append
    ctx.aico_progress_emit = progress.append
    profile = resolve_agent_runtime_profile("other")
    state = profile.configure_streaming(context=ctx, thread_id=None, correlation_id="c")
    profile.emit_progress(context=ctx)
    assert not state.stream_on
    assert emitted == []
    assert progress == []
    assert "_aico_stream_emitted" not in ctx.metadata


@pytest.mark.unit
def test_aico_profile_streaming_success_ndjson_shape():
    emitted: list[str] = []
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        roles=[],
        metadata={},
    )
    ctx.supports_aico_stream = True
    ctx.stream_emit = emitted.append
    profile = AicoRuntimeProfile()

    state = profile.configure_streaming(context=ctx, thread_id=None, correlation_id="corr")
    profile.emit_stream_result(
        state=state,
        result=FrameworkRunResult(ok=True, message="hello", final_phase="act"),
        thread_id=None,
        correlation_id="corr",
        fallback_message="fallback",
    )

    events = [json.loads(line) for line in emitted]
    assert events[0]["kind"] == "meta"
    assert events[0]["scope"] == "tick"
    assert events[0]["phase"] == "start"
    assert events[0]["client_hint"] == "running"
    assert events[1]["scope"] == "stream"
    assert events[2]["kind"] == "delta"
    assert events[-2]["kind"] == "end"
    assert events[-1]["scope"] == "tick"
    assert events[-1]["phase"] == "complete"
    assert events[-1]["ok"] is True
    assert ctx.metadata.get("_aico_stream_emitted") is True


@pytest.mark.unit
def test_aico_profile_streaming_failure_ndjson_shape():
    emitted: list[str] = []
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        roles=[],
        metadata={},
    )
    ctx.supports_aico_stream = True
    ctx.stream_emit = emitted.append
    profile = AicoRuntimeProfile()

    state = profile.configure_streaming(context=ctx, thread_id=None, correlation_id="corr")
    profile.emit_stream_result(
        state=state,
        result=FrameworkRunResult(ok=False, message="bad", final_phase="gate"),
        thread_id=None,
        correlation_id="corr",
        fallback_message="fallback",
    )

    events = [json.loads(line) for line in emitted]
    assert events[0]["phase"] == "start"
    assert events[1]["kind"] == "error"
    assert events[1]["code"] == "tick_failed"
    assert events[1]["message"] == "bad"


@pytest.mark.unit
def test_aico_profile_enter_tick_scope_sets_and_clears_full_chain_flag():
    cm = MagicMock()
    cm.get.return_value = {"enabled": True, "level": "DEBUG"}
    profile = AicoRuntimeProfile()

    assert is_aico_full_chain_tick() is False
    with profile.enter_tick_scope(config=cm):
        assert is_aico_full_chain_tick() is True
        assert should_emit_aico_full_chain_logs(cm) is True
    assert is_aico_full_chain_tick() is False


@pytest.mark.unit
def test_aico_framework_observability_sets_generic_and_aico_context():
    obs = AicoRuntimeProfile().build_framework_observability(config=object())

    assert get_agent_runtime_run_id_from_context() is None
    assert get_aico_run_id_from_context() is None
    with obs.run_scope(run_id="run-1", correlation_id="corr-1"):
        assert get_agent_runtime_run_id_from_context() == "run-1"
        assert get_agent_runtime_correlation_from_context() == "corr-1"
        assert get_aico_run_id_from_context() == "run-1"
        assert get_aico_correlation_from_context() == "corr-1"
    assert get_agent_runtime_run_id_from_context() is None
    assert get_agent_runtime_correlation_from_context() is None
    assert get_aico_run_id_from_context() is None
    assert get_aico_correlation_from_context() is None


@pytest.mark.unit
def test_aico_framework_observability_dispatches_http_exchange_logger(monkeypatch):
    calls: list[dict[str, object]] = []

    def fake_log_http_exchange(config, **kwargs):
        calls.append({"config": config, **kwargs})

    monkeypatch.setattr(
        "app.core.log.aico_observability.log_aico_http_exchange",
        fake_log_http_exchange,
    )
    obs = AicoRuntimeProfile().build_framework_observability(config=object())

    with obs.run_scope(run_id="run-1", correlation_id="corr-1"):
        log_agent_runtime_http_exchange(
            "config",
            url="https://llm.test",
            status_code=200,
            elapsed_ms=12.0,
            request_body={"q": "hi"},
            response_data={"ok": True},
        )

    assert calls == [
        {
            "config": "config",
            "url": "https://llm.test",
            "status_code": 200,
            "elapsed_ms": 12.0,
            "request_body": {"q": "hi"},
            "response_data": {"ok": True},
        }
    ]


@pytest.mark.unit
def test_http_error_logging_reads_generic_runtime_context(caplog):
    from app.game_engine.agent_runtime.llm_providers.http_utils import _log_llm_http_error

    logger_name = "test.agent_runtime.http"
    caplog.set_level(logging.ERROR, logger_name)

    with agent_runtime_observability_context(run_id="run-http", correlation_id="corr-http", logger_name=logger_name):
        _log_llm_http_error(
            url="https://llm.test",
            status_code=500,
            elapsed_ms=1.5,
            body={"model": "m"},
            response_text="boom",
        )

    assert "run_id=run-http correlation_id=corr-http" in caplog.text
    assert "llm_http_error" in caplog.text


@pytest.mark.unit
def test_aico_manifest_subset_uses_worker_frozen_tool_surface(monkeypatch):
    from app.game_engine.agent_runtime import aico_world_context
    from app.game_engine.agent_runtime import intent_classifier_interface

    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="corr-1",
        permissions=[],
        roles=[],
        metadata={"locale": "en"},
    )
    frozen_surface = ResolvedToolSurface(
        allowed_command_names=frozenset({"help"}),
        tool_command_context=ctx,
    )
    worker = SimpleNamespace(resolved_tool_surface=frozen_surface)
    cfg = SimpleNamespace(extra={"enable_intent_tool_manifest_subset": True})
    captured: dict[str, object] = {}

    def fake_classify_intent(*args, **kwargs):
        return SimpleNamespace(intent="informational")

    def fake_build_llm_tool_manifest(surface, command_registry, **kwargs):
        captured["surface"] = surface
        captured["locale"] = kwargs.get("locale")
        captured["manifest_interaction_filter"] = kwargs.get("manifest_interaction_filter")
        return ("manifest", [ToolSchema(name="help", description="Help")])

    monkeypatch.setattr(intent_classifier_interface, "classify_intent", fake_classify_intent)
    monkeypatch.setattr(aico_world_context, "build_llm_tool_manifest", fake_build_llm_tool_manifest)

    overrides = AicoRuntimeProfile().prepare_payload_overrides(
        session=None,
        node=SimpleNamespace(id=7),
        context=ctx,
        message="help",
        attrs={"tool_allowlist": ["look"]},
        cfg=cfg,
        worker=worker,
    )

    assert captured["surface"] is frozen_surface
    assert captured["locale"] == "en"
    assert captured["manifest_interaction_filter"] == "informational"
    assert overrides == {
        "tool_manifest_text": "manifest",
        "pdca_tool_schema_allowlist": ["help"],
    }


@pytest.mark.unit
def test_aico_manifest_subset_does_not_rebuild_without_worker_surface(monkeypatch):
    from app.game_engine.agent_runtime import aico_world_context
    from app.game_engine.agent_runtime import intent_classifier_interface

    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="corr-1",
        permissions=[],
        roles=[],
        metadata={},
    )
    cfg = SimpleNamespace(extra={"enable_intent_tool_manifest_subset": True})

    monkeypatch.setattr(
        intent_classifier_interface,
        "classify_intent",
        lambda *args, **kwargs: SimpleNamespace(intent="informational"),
    )

    def fail_build_llm_tool_manifest(*args, **kwargs):
        raise AssertionError("manifest subset must use worker.resolved_tool_surface only")

    monkeypatch.setattr(aico_world_context, "build_llm_tool_manifest", fail_build_llm_tool_manifest)

    overrides = AicoRuntimeProfile().prepare_payload_overrides(
        session=None,
        node=SimpleNamespace(id=7),
        context=ctx,
        message="help",
        attrs={"tool_allowlist": ["help"]},
        cfg=cfg,
        worker=SimpleNamespace(),
    )

    assert overrides == {}


@pytest.mark.unit
def test_npc_agent_nlp_tick_delegates_profile_hooks(monkeypatch):
    from app.commands.npc_agent_nlp import run_npc_agent_nlp_tick
    from app.game_engine.agent_runtime.frameworks.base import FrameworkRunResult
    from app.game_engine.agent_runtime.profiles.base import ProfileStreamState

    events: list[str] = []
    create_kwargs: dict[str, object] = {}

    class _Profile:
        service_id = "custom"

        def build_tick_hooks(self, *, config):
            events.append("build_tick_hooks")
            return "hooks"

        def build_framework_observability(self, *, config):
            events.append("build_framework_observability")
            return "observability"

        @contextmanager
        def enter_tick_scope(self, *, config):
            events.append("enter_scope")
            try:
                yield
            finally:
                events.append("exit_scope")

        def prepare_payload_overrides(self, **kwargs):
            events.append("prepare_payload")
            return {"tool_manifest_text": "profile-manifest"}

        def configure_streaming(self, **kwargs):
            events.append("configure_streaming")
            return ProfileStreamState()

        def emit_progress(self, **kwargs):
            events.append("emit_progress")

        def emit_stream_error(self, **kwargs):
            events.append("emit_stream_error")

        def emit_stream_result(self, **kwargs):
            events.append("emit_stream_result")

    class _Worker:
        tool_manifest_text = "worker-manifest"
        tool_schemas: list[object] = []

        def tick(self, payload, **kwargs):
            events.append("tick")
            assert payload["tool_manifest_text"] == "profile-manifest"
            return FrameworkRunResult(ok=True, message="ok", final_phase="act")

    profile = _Profile()
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.profiles.resolve_agent_runtime_profile",
        lambda service_id: profile,
    )
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.agent_llm_config.resolve_agent_llm_config_for_npc_tick",
        lambda *args, **kwargs: SimpleNamespace(extra={}, model=None, max_tokens=512),
    )
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.llm_client.http_llm_available",
        lambda cfg: True,
    )
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.llm_client.build_llm_client_from_service_config",
        lambda cfg: object(),
    )
    monkeypatch.setattr(
        "app.core.config_manager.get_config",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.agent_tick_context.build_caller_graph_snapshot",
        lambda session, context: CallerGraphSnapshot(1, 2, "Room"),
    )
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.aico_world_context.build_world_snapshot_from_session",
        lambda *args, **kwargs: "world",
    )

    def fake_create(*args, **kwargs):
        create_kwargs.update(kwargs)
        return _Worker()

    monkeypatch.setattr(
        "app.game_engine.agent_runtime.worker.LlmPdcaAssistantWorker.create",
        fake_create,
    )

    ctx = CommandContext(user_id="1", username="u", session_id="sess", permissions=[], roles=[], metadata={})
    node = SimpleNamespace(id=42, attributes={"service_id": "custom", "decision_mode": "llm"})

    res = run_npc_agent_nlp_tick(MagicMock(), node, ctx, "hello")

    assert res.ok
    assert create_kwargs["tick_hooks"] == "hooks"
    assert create_kwargs["runtime_observability"] == "observability"
    assert events == [
        "build_tick_hooks",
        "build_framework_observability",
        "enter_scope",
        "prepare_payload",
        "configure_streaming",
        "emit_progress",
        "tick",
        "emit_stream_result",
        "exit_scope",
    ]
