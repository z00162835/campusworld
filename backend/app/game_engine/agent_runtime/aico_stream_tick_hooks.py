"""Tick hooks that emit presentation-layer activity meta (not PDCA phase names)."""
from __future__ import annotations

from typing import Optional

from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.presentation_stream import ActivityKind
from app.game_engine.agent_runtime.thinking_pipeline import AgentTickHooks, ThinkingPhaseId


class AicoStreamTickHooks:
    """Emits ``scope=activity`` meta when presentation streaming is enabled."""

    def __init__(self, inner: Optional[AgentTickHooks] = None) -> None:
        self._inner = inner

    def on_before_phase(self, phase: ThinkingPhaseId, ctx: FrameworkRunContext) -> None:
        if self._inner is not None:
            self._inner.on_before_phase(phase, ctx)
        uvs = ctx.user_visible_stream
        if uvs is None:
            return
        coord = uvs.coordinator
        if phase in (ThinkingPhaseId.plan, ThinkingPhaseId.do, ThinkingPhaseId.check):
            coord.set_activity(ActivityKind.working)
        elif phase == ThinkingPhaseId.action:
            coord.set_activity(ActivityKind.working, detail='finalizing')

    def on_after_phase(
        self,
        phase: ThinkingPhaseId,
        ctx: FrameworkRunContext,
        *,
        phase_llm_output: str,
        skipped: bool = False,
    ) -> None:
        if self._inner is not None:
            self._inner.on_after_phase(phase, ctx, phase_llm_output=phase_llm_output, skipped=skipped)
