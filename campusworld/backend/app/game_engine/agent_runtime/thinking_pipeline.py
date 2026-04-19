"""Thinking model phase ids and optional tick hooks (F08 R4 / industry hooks alignment)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional, Protocol

from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext


class ThinkingPhaseId(str, Enum):
    """Logical phases for a sequential thinking pipeline (Pre…Post)."""

    pre = "pre"
    plan = "plan"
    do = "do"
    check = "check"
    action = "action"
    post = "post"


class AgentTickHooks(Protocol):
    """Cross-cutting hooks orthogonal to PhaseHandler bodies (logging, redaction, limits)."""

    def on_before_phase(
        self,
        phase: ThinkingPhaseId,
        ctx: FrameworkRunContext,
    ) -> None:
        ...

    def on_after_phase(
        self,
        phase: ThinkingPhaseId,
        ctx: FrameworkRunContext,
        *,
        phase_llm_output: str,
        skipped: bool = False,
    ) -> None:
        ...


class NoOpAgentTickHooks:
    def on_before_phase(self, phase: ThinkingPhaseId, ctx: FrameworkRunContext) -> None:
        return

    def on_after_phase(
        self,
        phase: ThinkingPhaseId,
        ctx: FrameworkRunContext,
        *,
        phase_llm_output: str,
        skipped: bool = False,
    ) -> None:
        return
