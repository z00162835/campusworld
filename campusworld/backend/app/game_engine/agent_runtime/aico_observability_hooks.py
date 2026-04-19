"""AgentTickHooks for AICO dedicated optimization log (see F03 §5.7)."""

from __future__ import annotations

import logging

from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.thinking_pipeline import ThinkingPhaseId


class AicoObservabilityTickHooks:
    """Logs tick boundaries and per-phase LLM output summaries to the AICO observability logger."""

    def __init__(
        self,
        logger: logging.Logger,
        *,
        max_phase_output_chars: int = 4000,
    ):
        self._log = logger
        self._max_phase_output_chars = max_phase_output_chars

    def _truncate(self, text: str) -> str:
        if not text:
            return ""
        m = self._max_phase_output_chars
        if m <= 0:
            return text
        if len(text) <= m:
            return text
        return text[:m] + "…"

    def on_before_phase(self, phase: ThinkingPhaseId, ctx: FrameworkRunContext) -> None:
        if phase != ThinkingPhaseId.plan:
            return
        msg = str(ctx.payload.get("message") or ctx.payload.get("text") or "")
        self._log.info(
            "aico_tick_start agent_node_id=%s correlation_id=%s user_message_chars=%s",
            ctx.agent_node_id,
            ctx.correlation_id,
            len(msg.strip()),
        )

    def on_after_phase(
        self,
        phase: ThinkingPhaseId,
        ctx: FrameworkRunContext,
        *,
        phase_llm_output: str,
        skipped: bool = False,
    ) -> None:
        out = phase_llm_output or ""
        preview = self._truncate(out).replace("\n", "\\n")
        self._log.info(
            "aico_phase_end phase=%s agent_node_id=%s correlation_id=%s skipped=%s output_chars=%s output_preview=%s",
            phase.value,
            ctx.agent_node_id,
            ctx.correlation_id,
            skipped,
            len(out),
            preview,
        )
