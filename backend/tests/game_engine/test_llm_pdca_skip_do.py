"""Tests for ``phase_llm.do.mode: skip`` — user text is Plan prose only (AGENT_PDCA)."""

from __future__ import annotations

import pytest

from app.commands.base import CommandContext, CommandResult
from app.core.settings import AgentLlmServiceConfig, PhaseLlmMode, PhaseLlmPhaseConfig
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.frameworks.llm_pdca import (
    LlmPDCAFramework,
    assemble_plan_skip_do_draft,
)
from app.game_engine.agent_runtime.resolved_tool_surface import PreauthorizedToolExecutor, ResolvedToolSurface
from app.game_engine.agent_runtime.tool_gather import (
    format_gathered_observations_for_end_user,
    format_tool_observation_block,
)


class _FakeMem:
    def start_run(self, *args, **kwargs):
        pass

    def update_run(self, *args, **kwargs):
        pass

    def finish_run(self, *args, **kwargs):
        pass

    def append_raw(self, *args, **kwargs):
        pass


@pytest.mark.unit
def test_assemble_plan_skip_do_draft_plain_plan_only() -> None:
    assert assemble_plan_skip_do_draft("  hello  ", "") == "hello"


@pytest.mark.unit
def test_assemble_plan_skip_do_draft_ignores_observations_for_user() -> None:
    """Observations are not concatenated into SSH/user-visible draft."""
    assert assemble_plan_skip_do_draft("", "  obs-text  ") == ""
    assert assemble_plan_skip_do_draft("Summary.", "cmd-out") == "Summary."


@pytest.mark.unit
def test_format_gathered_observations_for_end_user_strips_f08_frames() -> None:
    block = format_tool_observation_block(
        1,
        "whoami",
        [],
        CommandResult.success_result("当前用户：admin"),
    )
    plain = format_gathered_observations_for_end_user(block)
    assert "tool_observation" not in plain.lower()
    assert "whoami" in plain
    assert "当前用户：admin" in plain


@pytest.mark.unit
def test_assemble_plan_skip_do_draft_strips_plan_only_even_with_f08_block() -> None:
    block = format_tool_observation_block(
        1,
        "whoami",
        [],
        CommandResult.success_result("当前用户：admin"),
    )
    assert assemble_plan_skip_do_draft("你是 admin。", block) == "你是 admin。"


@pytest.mark.unit
def test_skip_do_single_plan_llm_check_skipped() -> None:
    """Do + Check skipped: only Plan calls ``complete``."""

    class _Scripted:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, *, system: str, user: str, call_spec=None) -> str:
            self.calls += 1
            return "plan-only-reply"

    llm = _Scripted()
    fw = LlmPDCAFramework(
        memory=_FakeMem(),
        llm_config=AgentLlmServiceConfig(
            system_prompt="Sys.",
            phase_prompts={"plan": "P", "do": "D", "check": "C", "act": "A"},
        ),
        instance_phase_llm={
            "do": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            "check": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
        },
        instance_mode_models={},
        llm=llm,
    )
    out = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    assert out.ok
    assert llm.calls == 1
    assert out.message == "plan-only-reply"


@pytest.mark.unit
def test_skip_do_with_plan_tools_user_sees_plan_prose_only(monkeypatch) -> None:
    """Plan runs JSON tool then text; user message is final Plan prose, not tool blocks."""

    class _JsonThenText:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, *, system: str, user: str, call_spec=None) -> str:
            self.calls += 1
            if self.calls == 1:
                return '{"commands": [{"name": "help", "args": []}]}'
            return "wrapped-up"

    class _HelpCmd:
        name = "help"

        def execute(self, _ctx, args):
            return CommandResult.success_result("HELP_BODY")

    monkeypatch.setattr(
        "app.game_engine.agent_runtime.resolved_tool_surface.command_registry.get_command",
        lambda _name: _HelpCmd(),
    )

    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        roles=[],
    )
    surface = ResolvedToolSurface(
        allowed_command_names=frozenset({"help"}),
        tool_command_context=ctx,
    )
    pre = PreauthorizedToolExecutor(surface)

    llm = _JsonThenText()
    fw = LlmPDCAFramework(
        memory=_FakeMem(),
        llm_config=AgentLlmServiceConfig(
            system_prompt="Sys.",
            phase_prompts={"plan": "P", "do": "D", "check": "C", "act": "A"},
        ),
        instance_phase_llm={
            "do": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            "check": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
        },
        instance_mode_models={},
        llm=llm,
        tools=pre,
        tool_command_context=ctx,
        preauthorized_tool_executor=pre,
    )
    out = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    assert out.ok
    assert (out.message or "") == "wrapped-up"
    assert "Tool observations" not in (out.message or "")
    assert "tool_observation begin" not in (out.message or "")
    assert "HELP_BODY" not in (out.message or "")


@pytest.mark.unit
def test_check_retry_with_skip_do_replans_without_second_check_llm() -> None:
    """Check RETRY replans once; framework does not run Check again after retry (same as Do path)."""

    class _Scripted:
        def __init__(self, script: list[str]) -> None:
            self._script = list(script)
            self.calls = 0

        def complete(self, *, system: str, user: str, call_spec=None) -> str:
            if self.calls < len(self._script):
                out = self._script[self.calls]
            else:
                out = ""
            self.calls += 1
            return out

    # plan → check (RETRY) → plan retry — no second Check LLM in ``_run_inner``.
    script = [
        "plan-a",
        "RETRY: need_tools=whoami",
        "plan-retry-b",
    ]
    llm = _Scripted(script)
    fw = LlmPDCAFramework(
        memory=_FakeMem(),
        llm_config=AgentLlmServiceConfig(
            system_prompt="Sys.",
            phase_prompts={"plan": "P", "do": "D", "check": "C", "act": "A"},
        ),
        instance_phase_llm={
            "do": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
        },
        instance_mode_models={},
        llm=llm,
    )
    out = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    assert out.ok
    assert llm.calls == 3
    assert out.message == "plan-retry-b"
