"""
Core LLM types and wiring for agent runtime.

- ``LlmCallSpec`` / ``LlmClient`` / ``StubLlmClient`` — shared contracts
- ``http_llm_available`` / ``build_llm_client_from_service_config`` — config + env gate

Vendor-specific HTTP clients live under ``llm_providers/``; routing is in ``llm_providers/factory.py``.
Shared HTTP helpers: ``llm_providers/http_utils.py``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Sequence, runtime_checkable

from app.core.settings import PhaseLlmMode


@dataclass
class LlmCallSpec:
    """Per-call options for one PDCA phase (merged from YAML + tick overrides)."""

    mode: PhaseLlmMode = PhaseLlmMode.plan
    model: str = ""
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    timeout_sec: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LlmClient(Protocol):
    """LLM surface for agent frameworks; supports per-phase call_spec.

    All provider clients must implement :meth:`complete` (plain text). The
    optional methods :meth:`supports_tools` / :meth:`complete_with_tools`
    let the framework choose between native function-calling and the JSON
    fallback without knowing the vendor. Defaults (provided by
    :func:`_default_supports_tools`) keep every existing client safe.
    """

    def complete(self, *, system: str, user: str, call_spec: Optional[LlmCallSpec] = None) -> str:
        """Return assistant text for one user turn (non-streaming)."""
        ...


def supports_tools(client: "LlmClient") -> bool:
    """Ask a client whether it implements native tool-use.

    Default answer is ``False`` — the method is optional, so clients that
    predate the contract continue to work unchanged.
    """
    fn = getattr(client, "supports_tools", None)
    if callable(fn):
        try:
            return bool(fn())
        except Exception:
            return False
    return False


def complete_with_tools(
    client: "LlmClient",
    *,
    system: str,
    turns: Sequence[Any],
    tools: Sequence[Any],
    call_spec: Optional[LlmCallSpec] = None,
):
    """Invoke native tool-use on a client or raise ``NotImplementedError``.

    ``turns`` is a sequence of :class:`ConversationTurn` instances from
    :mod:`app.game_engine.agent_runtime.tool_calling` (``TextTurn``,
    ``AssistantToolUseTurn``, ``ToolResultsTurn``); ``tools`` a sequence
    of :class:`ToolSchema`. The return type is
    :class:`CompleteWithToolsResult`.
    """
    fn = getattr(client, "complete_with_tools", None)
    if not callable(fn):
        raise NotImplementedError(
            f"{type(client).__name__} does not implement complete_with_tools"
        )
    return fn(system=system, turns=list(turns), tools=list(tools), call_spec=call_spec)


class StubLlmClient:
    """Deterministic stub when no provider is configured (tests and dev).

    Declares ``supports_tools() == False`` so the framework routes through
    the JSON fallback path; this keeps the JSON parser exercised in tests.
    """

    def complete(self, *, system: str, user: str, call_spec: Optional[LlmCallSpec] = None) -> str:
        u = (user or "").strip()
        mode = (call_spec.mode.value if call_spec else "plan") if call_spec else "plan"
        if len(u) > 400:
            u = u[:400] + "…"
        return f"[stub_llm mode={mode}] {u}"

    def supports_tools(self) -> bool:
        return False


def http_llm_available(cfg) -> bool:
    """True when config requests HTTP LLM and the referenced API key env var is non-empty."""
    from app.core.settings import AgentLlmServiceConfig

    if not isinstance(cfg, AgentLlmServiceConfig):
        return False
    env_name = (cfg.api_key_env or "").strip()
    key = os.environ.get(env_name, "").strip() if env_name else ""
    return bool(cfg.use_http_llm and env_name and key)


def build_llm_client_from_service_config(cfg) -> LlmClient:
    """
    Resolve Stub vs HTTP from ``AgentLlmServiceConfig`` + environment.

    HTTP implementation is selected in ``llm_providers.factory.build_http_llm_client``.
    """
    from app.core.settings import AgentLlmServiceConfig

    if not isinstance(cfg, AgentLlmServiceConfig):
        return StubLlmClient()
    if http_llm_available(cfg):
        env_name = (cfg.api_key_env or "").strip()
        key = os.environ.get(env_name, "").strip() if env_name else ""
        from app.game_engine.agent_runtime.llm_providers.factory import build_http_llm_client

        return build_http_llm_client(cfg, key)
    return StubLlmClient()
