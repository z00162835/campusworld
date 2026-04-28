"""Provider-agnostic tool-calling primitives for the agent runtime.

The framework and agent-runtime context helpers work exclusively with the dataclasses
in this module. Provider adapters (MiniMax Anthropic, OpenAI-compatible,
MiniMax native) are responsible for mapping these to vendor wire formats
and back.

Design:
  * ``ToolSchema`` — neutral description of one callable command (name,
    human description, JSON Schema for inputs). The default ``args_only``
    schema treats a CampusWorld command as ``{"args": ["..."]}``, which is
    the exact shape ``BaseCommand.execute(context, args: List[str])``
    expects.
  * ``ToolCall`` — one invocation (id + name + positional args).
  * ``ToolResult`` — one observation (id + ok + text + optional data).
  * ``ConversationTurn`` — ``TextTurn``, ``AssistantToolUseTurn``, or
    ``ToolResultsTurn``; lets the framework pass a transcript to
    ``complete_with_tools`` without knowing the provider's wire format.
    ``AssistantToolUseTurn`` records the model's tool invocations (ids +
    names + args) so adapters can emit a valid assistant ``tool_use``
    message **before** the following ``ToolResultsTurn`` (required by
    Anthropic-style APIs; not MiniMax-specific).
  * ``CompleteWithToolsResult`` — uniform return type from
    ``LlmClient.complete_with_tools``.

Mapping helpers bridge this module to ``tool_gather.ToolInvocationPlan`` and
``CommandResult`` without touching any provider-specific code.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union


def _args_only_schema() -> Dict[str, Any]:
    """JSON Schema for the default CampusWorld command input (``{args: [...]}``)."""
    return {
        "type": "object",
        "properties": {
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Positional arguments passed to the command, as strings.",
            }
        },
        "required": [],
        "additionalProperties": False,
    }


@dataclass(frozen=True)
class ToolSchema:
    """Neutral description of one tool (command) that can be called."""

    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=_args_only_schema)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": dict(self.input_schema),
        }


@dataclass
class ToolCall:
    """One tool invocation produced by the LLM or parsed from JSON output."""

    id: str
    name: str
    args: List[str] = field(default_factory=list)

    @classmethod
    def new(cls, name: str, args: Optional[Sequence[str]] = None) -> "ToolCall":
        return cls(id=f"call_{uuid.uuid4().hex[:12]}", name=str(name), args=list(args or []))


@dataclass
class ToolResult:
    """Observation returned by executing a ``ToolCall``."""

    id: str
    name: str
    ok: bool
    text: str
    data: Optional[Dict[str, Any]] = None


@dataclass
class TextTurn:
    """Plain user/assistant text turn in the conversation history."""

    role: str  # "user" or "assistant"
    text: str


@dataclass
class ToolResultsTurn:
    """Batch of tool observations returned to the model in one turn."""

    results: List[ToolResult] = field(default_factory=list)


@dataclass
class AssistantToolUseTurn:
    """Assistant turn that selected one or more tools (provider-neutral).

    Invariant for multi-turn native tool protocols: this turn must be
    immediately followed by a :class:`ToolResultsTurn` whose
    ``ToolResult.id`` values match the ``ToolCall.id`` values here (same
    order when multiple calls are batched).

    ``text`` is optional co-prose from the model; it may be empty when the
    model emitted only tool calls.
    """

    tool_calls: List[ToolCall] = field(default_factory=list)
    text: str = ""


# Union alias for readability in signatures.
ConversationTurn = Union[TextTurn, ToolResultsTurn, AssistantToolUseTurn]


@dataclass
class CompleteWithToolsResult:
    """Uniform response from ``LlmClient.complete_with_tools``.

    ``tool_calls`` is empty when the model chose to answer with plain text.
    ``finish_reason`` is provider-reported (``tool_use`` / ``tool_calls`` /
    ``stop`` / ``end_turn`` / …); framework only looks at whether
    ``tool_calls`` is non-empty and at the literal strings ``tool_use`` or
    ``tool_calls`` for "do not also parse JSON" branching.
    """

    text: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"


# ---------- mapping helpers (framework / command layer bridge) ----------


def tool_calls_to_invocation_plan(calls: Sequence[ToolCall]):
    """Turn neutral ``ToolCall`` list into the existing ``ToolInvocationPlan``.

    Lives here (not in ``tool_gather``) so ``tool_gather`` stays unaware of
    provider tool-use; this module is the only provider-neutral adapter.
    """
    from app.game_engine.agent_runtime.tool_gather import ToolInvocationPlan

    commands = [(c.name, list(c.args)) for c in calls]
    return ToolInvocationPlan(commands=commands)


def command_result_to_tool_result(
    call_id: str,
    name: str,
    result,
    *,
    max_text_chars: int = 4000,
) -> ToolResult:
    """Shrink a ``CommandResult`` to a ``ToolResult`` envelope for the LLM."""
    ok = bool(getattr(result, "success", False))
    msg = str(getattr(result, "message", "") or "")
    if len(msg) > max_text_chars:
        msg = msg[: max_text_chars - 3] + "..."
    data = getattr(result, "data", None)
    if not isinstance(data, dict):
        data = None
    return ToolResult(id=call_id, name=name, ok=ok, text=msg, data=data)


def tool_schemas_from_surface(surface, command_registry) -> List[ToolSchema]:
    """Build ``ToolSchema`` list from a ``ResolvedToolSurface``.

    Initial seed: ``BaseCommand.description`` or ``get_help()`` one-liner.
    For AICO, :func:`app.game_engine.agent_runtime.aico_world_context.build_llm_tool_manifest`
    overwrites each description using ``tool_manifest_locale()`` (``app.default_locale``)
    plus graph ``llm_hint*`` before the worker exposes tools to the LLM.
    """
    schemas: List[ToolSchema] = []
    for name in sorted(surface.allowed_command_names):
        cmd = command_registry.get_command(name)
        if cmd is None:
            continue
        desc = (getattr(cmd, "description", "") or "").strip() or cmd.get_help().strip()
        if len(desc) > 400:
            desc = desc[:397] + "..."
        schemas.append(ToolSchema(name=name, description=desc))
    return schemas


def assistant_tool_use_turn_as_text_block(turn: AssistantToolUseTurn) -> str:
    """Serialise an ``AssistantToolUseTurn`` for the JSON / plain ``complete`` fallback."""
    lines: List[str] = []
    if (turn.text or "").strip():
        lines.append((turn.text or "").strip())
    for c in turn.tool_calls:
        lines.append(f"[tool_use id={c.id!r} name={c.name!r} args={c.args!r}]")
    return "\n".join(lines) if lines else "(assistant tool_use)"


def tool_results_turn_as_text_block(turn: ToolResultsTurn) -> str:
    """Serialise a ``ToolResultsTurn`` as the legacy ``Tool observations`` text block.

    Used by the framework as the fallback representation when the LLM
    client does not support native tool use — keeps a single source of
    truth for observation formatting.
    """
    if not turn.results:
        return ""
    lines: List[str] = []
    for idx, r in enumerate(turn.results, start=1):
        lines.append("--- tool_observation begin ---")
        lines.append(f"[{idx}] command={r.name}")
        lines.append(f"ok={r.ok}")
        lines.append("message:")
        lines.append(r.text or "")
        if r.data:
            flat = ", ".join(f"{k}={r.data[k]!r}" for k in sorted(r.data.keys()))
            lines.append(f"data: {flat}")
        lines.append("--- tool_observation end ---")
    return "\n".join(lines)
