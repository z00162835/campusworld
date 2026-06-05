from __future__ import annotations

from typing import List, Optional, Sequence

from app.game_engine.agent_runtime.agent_loop.signals import PendingToolWork
from app.game_engine.agent_runtime.tool_calling import ToolCall

_TOOL_USE_FINISH = frozenset({'tool_use', 'tool_calls'})


def detect_pending_tool_work(
    *,
    calls: Sequence[ToolCall],
    dropped_names: Sequence[str],
    finish_reason: Optional[str],
    pre_filter_calls: Sequence[ToolCall],
) -> Optional[PendingToolWork]:
    """Return pending tool work when the model intended tools but execution cannot proceed yet."""
    dropped = [str(x).strip() for x in dropped_names if str(x).strip()]
    fr = (finish_reason or '').strip().lower()
    reasons: List[str] = []
    if dropped:
        reasons.append('tools_filtered')
    if fr in _TOOL_USE_FINISH and not calls:
        reasons.append('tool_use_filtered_empty')
    if pre_filter_calls and not calls and not dropped:
        reasons.append('tool_calls_unavailable')
    if not reasons:
        return None
    return PendingToolWork(reason_codes=reasons, dropped_names=dropped, finish_reason=finish_reason)


def should_exit_react_round(*, calls: Sequence[ToolCall], pending: Optional[PendingToolWork]) -> bool:
    """True when this round may end without executing or continuing tools."""
    if calls:
        return False
    if pending is not None:
        return False
    return True
