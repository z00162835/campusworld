from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.game_engine.agent_runtime.presentation_stream import UserVisibleStream

@dataclass
class FrameworkRunContext:
    """Inputs for one agent tick (command-triggered or queue)."""
    agent_node_id: int
    correlation_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    system_prompt: Optional[str] = None
    phase_prompts: Dict[str, str] = field(default_factory=dict)
    memory_context: Optional[str] = None
    recent_conversation: Optional[str] = None
    retrieved_memory: Optional[str] = None
    memory_context_do: Optional[str] = None
    phase_llm_overrides: Dict[str, Any] = field(default_factory=dict)
    user_visible_stream: Optional['UserVisibleStream'] = None
    stream_cancel_check: Optional[Callable[[], bool]] = None
    # Phase whose prose becomes FrameworkRunResult.message; sole presentation stream source.
    presentation_anchor_phase: Optional[str] = None

@dataclass
class FrameworkRunResult:
    ok: bool
    message: str = ''
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
