from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FrameworkRunContext:
    """Inputs for one agent tick (command-triggered or queue)."""

    agent_node_id: int
    correlation_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    # Optional NL + LLM + PDCA overrides per tick; base prompts live in YAML.
    system_prompt: Optional[str] = None
    phase_prompts: Dict[str, str] = field(default_factory=dict)
    memory_context: Optional[str] = None
    #: When set with retrieved_memory, Plan orders STM then LTM per F12 §7; else memory_context alone (legacy).
    recent_conversation: Optional[str] = None
    retrieved_memory: Optional[str] = None
    #: When set, Do / Check phases use this instead of repeating full STM/LTM (F12 D5).
    memory_context_do: Optional[str] = None
    # Raw dict per phase -> merged into PhaseLlmPhaseConfig (tick-level phase_llm overrides)
    phase_llm_overrides: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FrameworkRunResult:
    ok: bool
    message: str = ""
    final_phase: Optional[str] = None


class ThinkingFramework(ABC):
    """Pluggable cognition main loop (PDCA, OODA, …)."""

    @abstractmethod
    def run(self, ctx: FrameworkRunContext) -> FrameworkRunResult:
        raise NotImplementedError

    @property
    @abstractmethod
    def framework_id(self) -> str:
        raise NotImplementedError
