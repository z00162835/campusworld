from __future__ import annotations

from typing import List, Sequence, Tuple

from app.game_engine.agent_runtime.tool_calling import (
    AssistantToolUseTurn,
    ConversationTurn,
    TextTurn,
    ToolCall,
    ToolResult,
    ToolResultsTurn,
)


def _filtered_tool_message(dropped_names: Sequence[str]) -> str:
    names = ', '.join(sorted({str(n).strip() for n in dropped_names if str(n).strip()}))
    return (
        f'[tool error] The following tools are not available in this turn\'s Tools available list: {names}. '
        'Use only tools listed in the manifest for this request (for example find, describe, primer).'
    )


def build_filtered_tool_continuation_turns(
    *,
    pre_filter_calls: Sequence[ToolCall],
    dropped_names: Sequence[str],
    assistant_text: str = '',
) -> List[ConversationTurn]:
    """Build assistant tool_use + synthetic error tool_result turns after schema filtering."""
    dropped_set = {str(n).strip().lower() for n in dropped_names if str(n).strip()}
    blocked: List[ToolCall] = []
    for call in pre_filter_calls:
        raw = (call.name or '').strip()
        if raw.lower() in dropped_set or raw in dropped_names:
            blocked.append(call)
    if not blocked and pre_filter_calls and dropped_names:
        blocked = list(pre_filter_calls)
    if not blocked:
        return [TextTurn(role='user', text=_filtered_tool_message(dropped_names))]
    results: List[ToolResult] = []
    err_text = _filtered_tool_message(dropped_names)
    for (i, call) in enumerate(blocked):
        cid = (call.id or '').strip() or f'filtered_{i}'
        results.append(ToolResult(id=cid, name=call.name, ok=False, text=err_text))
    return [
        AssistantToolUseTurn(text=assistant_text or '', tool_calls=[ToolCall(id=c.id, name=c.name, args=list(c.args)) for c in blocked]),
        ToolResultsTurn(results=results),
    ]


def build_draft_retry_user_text(*, reason_code: str = 'draft_incomplete:deferral') -> str:
    if reason_code == 'draft_incomplete:deferral':
        return (
            'Your last reply looks like an interim status message rather than a final answer. '
            'Continue calling read-only tools as needed, then provide a complete user-facing reply grounded in tool observations. '
            'Do not end with phrases like "I will query" or "let me check" without substantive results.'
        )
    return (
        'The draft is incomplete for this request. Gather missing information with available tools, '
        'then provide a complete grounded reply.'
    )
