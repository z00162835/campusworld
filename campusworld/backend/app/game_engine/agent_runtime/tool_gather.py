"""ToolGather: execute ToolInvocation plans and format ToolObservation blocks (F08)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from app.commands.base import CommandContext, CommandResult
from app.game_engine.agent_runtime.tooling import ToolExecutor

# Keys allowed to appear in ToolObservation from CommandResult.data (F08 §8).
DEFAULT_TOOL_OBSERVATION_DATA_KEYS: FrozenSet[str] = frozenset(
    {"ok", "phase", "handle", "service_id"}
)


@dataclass
class ToolInvocationPlan:
    """0..N command invocations produced by a phase selector or parsed LLM output."""

    commands: List[Tuple[str, List[str]]] = field(default_factory=list)


@dataclass
class ToolGatherBudgets:
    """Caps for one tick; phase-level limits may further slice via caller."""

    max_commands_per_tick: int = 16
    max_chars_observations_per_tick: int = 12000
    max_commands_per_phase: int = 8
    max_tool_rounds_per_phase: int = 1


@dataclass
class ToolGatherCounters:
    commands_run: int = 0
    observation_chars: int = 0


def tool_gather_budgets_from_agent_extra(extra: Optional[Dict[str, Any]]) -> ToolGatherBudgets:
    """Build budgets from ``agents.llm`` YAML ``extra`` (optional keys)."""
    ex = extra or {}
    return ToolGatherBudgets(
        max_commands_per_tick=int(ex.get("tool_gather_max_commands_tick", 16)),
        max_chars_observations_per_tick=int(ex.get("tool_gather_max_chars_tick", 12000)),
        max_commands_per_phase=int(ex.get("tool_gather_max_commands_phase", 8)),
        max_tool_rounds_per_phase=int(ex.get("tool_gather_max_rounds_per_phase", 1)),
    )


def parse_tool_invocation_plan_from_text(text: str) -> ToolInvocationPlan:
    """
    Extract first JSON object with a \"commands\" array from LLM output (F08 §7).
    Each item: {\"name\": \"cmd\", \"args\": [...]}.
    """
    if not (text or "").strip():
        return ToolInvocationPlan()
    # Prefer fenced ```json blocks
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    candidate = fence.group(1).strip() if fence else text.strip()
    obj = _try_parse_json_object(candidate)
    if obj is None:
        # Scan for outermost {...} containing "commands"
        m = re.search(r"\{[\s\S]*\"commands\"[\s\S]*\}", text)
        if m:
            obj = _try_parse_json_object(m.group(0))
    if obj is None or not isinstance(obj, dict):
        return ToolInvocationPlan()
    raw = obj.get("commands")
    if not isinstance(raw, list):
        return ToolInvocationPlan()
    out: List[Tuple[str, List[str]]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().lower()
        if not name:
            continue
        args_raw = item.get("args")
        args: List[str]
        if args_raw is None:
            args = []
        elif isinstance(args_raw, list):
            args = [str(a) for a in args_raw]
        else:
            args = [str(args_raw)]
        out.append((name, args))
    return ToolInvocationPlan(commands=out)


def _try_parse_json_object(s: str) -> Optional[Dict[str, Any]]:
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else None
    except json.JSONDecodeError:
        return None


def _format_data_subset(data: Optional[Dict[str, Any]], allowed_keys: FrozenSet[str]) -> str:
    if not data or not allowed_keys:
        return ""
    parts: List[str] = []
    for k in sorted(data.keys()):
        if k in allowed_keys:
            parts.append(f"{k}={data[k]!r}")
    if not parts:
        return ""
    return "data: " + ", ".join(parts)


def format_tool_observation_block(
    index: int,
    command_name: str,
    args: List[str],
    result: CommandResult,
    *,
    data_keys: Optional[FrozenSet[str]] = None,
    max_message_chars: int = 4000,
) -> str:
    """F08 appendix A style single observation."""
    keys = data_keys if data_keys is not None else DEFAULT_TOOL_OBSERVATION_DATA_KEYS
    ok = result.success
    msg = str(result.message or "")
    if len(msg) > max_message_chars:
        msg = msg[: max_message_chars - 3] + "..."
    extra = _format_data_subset(result.data if isinstance(result.data, dict) else None, keys)
    lines = [
        f"--- tool_observation begin ---",
        f"[{index}] command={command_name} args={args!r}",
        f"ok={ok}",
        "message:",
        msg,
    ]
    if extra:
        lines.append(extra)
    lines.append("--- tool_observation end ---")
    return "\n".join(lines)


def gather_tool_observations(
    executor: ToolExecutor,
    tool_context: CommandContext,
    plan: ToolInvocationPlan,
    *,
    budgets: ToolGatherBudgets,
    counters: ToolGatherCounters,
    phase_label: str,
    data_keys: Optional[FrozenSet[str]] = None,
    trace_prefix: str = "tool",
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Execute plan commands in order; return concatenated observation text and trace entries for command_trace.
    """
    chunks: List[str] = []
    trace_entries: List[Dict[str, Any]] = []
    idx = 0
    phase_cmds = 0
    for command_name, args in plan.commands:
        if counters.commands_run >= budgets.max_commands_per_tick:
            trace_entries.append(
                {"step": f"{trace_prefix}_cap", "detail": "tick_max_commands", "phase": phase_label}
            )
            break
        if phase_cmds >= budgets.max_commands_per_phase:
            trace_entries.append(
                {"step": f"{trace_prefix}_cap", "detail": "phase_max_commands", "phase": phase_label}
            )
            break
        idx += 1
        res = executor.execute_command(tool_context, command_name, args)
        counters.commands_run += 1
        phase_cmds += 1
        block = format_tool_observation_block(
            idx, command_name, args, res, data_keys=data_keys
        )
        obs_len = len(block)
        if counters.observation_chars + obs_len > budgets.max_chars_observations_per_tick:
            trace_entries.append(
                {"step": f"{trace_prefix}_cap", "detail": "tick_max_chars", "phase": phase_label}
            )
            break
        counters.observation_chars += obs_len
        chunks.append(block)
        trace_entries.append(
            {
                "step": f"{trace_prefix}_exec",
                "phase": phase_label,
                "command_name": command_name,
                "args": args,
                "success": res.success,
                "message_len": len(str(res.message or "")),
            }
        )
    text = "\n\n".join(chunks)
    return text, trace_entries

