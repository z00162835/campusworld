"""Adapter protocol for agent tool-use evaluation."""
from __future__ import annotations

from typing import Protocol

from app.game_engine.agent_runtime.eval.schema import AgentToolEvalCase, EvalPrediction


class AgentEvalAdapter(Protocol):
    """Agent-specific bridge into the generic eval runner."""

    adapter_name: str

    def run_live_case(self, case: AgentToolEvalCase) -> EvalPrediction:
        """Run the real agent command path and return DB/log-backed evidence."""
        ...
