"""Minimal strategy hooks for npc_agent NLP runtime profiles."""
from __future__ import annotations
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any, Callable, ContextManager, Dict, Optional, Protocol

from app.commands.base import CommandContext
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunResult
from app.game_engine.agent_runtime.observability import AgentRuntimeObservability, NoopAgentRuntimeObservability
from app.game_engine.agent_runtime.thinking_pipeline import AgentTickHooks


@dataclass
class ProfileStreamState:
    stream_on: bool = False
    tick_started: bool = False
    emit: Optional[Callable[[str], None]] = None


class AgentRuntimeProfile(Protocol):
    service_id: str

    def prepare_payload_overrides(self, *, session: Any, node: Any, context: CommandContext, message: str, attrs: Dict[str, Any], cfg: Any, worker: Any) -> Dict[str, Any]:
        ...

    def build_tick_hooks(self, *, config: Any) -> Optional[AgentTickHooks]:
        ...

    def build_framework_observability(self, *, config: Any) -> AgentRuntimeObservability:
        ...

    def enter_tick_scope(self, *, config: Any) -> ContextManager[None]:
        ...

    def enable_full_chain_logs(self, *, config: Any) -> bool:
        ...

    def configure_streaming(self, *, context: CommandContext, thread_id: Any, correlation_id: Optional[str]) -> ProfileStreamState:
        ...

    def emit_progress(self, *, context: CommandContext) -> None:
        ...

    def emit_stream_error(self, *, state: ProfileStreamState, code: str, message: str) -> None:
        ...

    def emit_stream_result(self, *, state: ProfileStreamState, result: FrameworkRunResult, thread_id: Any, correlation_id: Optional[str], fallback_message: str) -> None:
        ...


class NoopAgentRuntimeProfile:
    service_id = '*'

    def prepare_payload_overrides(self, *, session: Any, node: Any, context: CommandContext, message: str, attrs: Dict[str, Any], cfg: Any, worker: Any) -> Dict[str, Any]:
        return {}

    def build_tick_hooks(self, *, config: Any) -> Optional[AgentTickHooks]:
        return None

    def build_framework_observability(self, *, config: Any) -> AgentRuntimeObservability:
        _ = config
        return NoopAgentRuntimeObservability()

    def enter_tick_scope(self, *, config: Any) -> ContextManager[None]:
        _ = config
        return nullcontext()

    def enable_full_chain_logs(self, *, config: Any) -> bool:
        return False

    def configure_streaming(self, *, context: CommandContext, thread_id: Any, correlation_id: Optional[str]) -> ProfileStreamState:
        return ProfileStreamState()

    def emit_progress(self, *, context: CommandContext) -> None:
        return None

    def emit_stream_error(self, *, state: ProfileStreamState, code: str, message: str) -> None:
        return None

    def emit_stream_result(self, *, state: ProfileStreamState, result: FrameworkRunResult, thread_id: Any, correlation_id: Optional[str], fallback_message: str) -> None:
        return None
