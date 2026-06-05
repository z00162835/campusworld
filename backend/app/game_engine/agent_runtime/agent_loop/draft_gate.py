from __future__ import annotations

import re
from typing import List, Optional, Sequence

from app.game_engine.agent_runtime.agent_loop.config import AgentLoopConfig
from app.game_engine.agent_runtime.agent_loop.signals import DraftCompletenessVerdict, DraftReasonContext
from app.game_engine.agent_runtime.tool_calling import ToolResult

_DEFAULT_DEFERRAL_PATTERNS = (
    r'我先',
    r'让我(?:先)?查(?:询|一下)',
    r'稍等',
    r'正在查',
    r"(?i)\blet me check\b",
    r"(?i)\bi['']?ll (?:look up|query|check)\b",
    r"(?i)\bi will (?:look up|query|check)\b",
)

_GROUNDING_TOOL_NAMES = frozenset({'find', 'describe', 'primer', 'look', 'space', 'help', 'whoami', 'agent'})

_CHITCHAT_PATTERNS = (
    r'^(?:thanks|thank you|thx|ok|okay|好的|谢谢|收到)[!.?]*$',
    r'^(?:hi|hello|hey|你好)[!.?]*$',
)

_WORLD_INTRO_PATTERN = re.compile(
    r'(?:介绍|介绍一下|introduce|tell me about).*(?:hicampus|世界|world|campus)',
    flags=re.IGNORECASE,
)


def _deferral_patterns(config: AgentLoopConfig) -> Sequence[str]:
    if config.deferral_patterns:
        return config.deferral_patterns
    return _DEFAULT_DEFERRAL_PATTERNS


def is_deferral_prose(text: str, *, config: AgentLoopConfig) -> bool:
    stripped = (text or '').strip()
    if not stripped:
        return False
    for pat in _deferral_patterns(config):
        if re.search(pat, stripped, flags=re.IGNORECASE):
            return True
    return False


def has_successful_grounding_obs(tool_results: Sequence[ToolResult]) -> bool:
    for r in tool_results:
        if not r.ok:
            continue
        name = (r.name or '').strip().lower()
        if name in _GROUNDING_TOOL_NAMES:
            return True
    return False


def _is_chitchat(user_message: str) -> bool:
    text = (user_message or '').strip()
    if not text:
        return True
    for pat in _CHITCHAT_PATTERNS:
        if re.match(pat, text, flags=re.IGNORECASE):
            return True
    return False


def _needs_runtime_grounding(user_message: str, *, context: Optional[DraftReasonContext]) -> bool:
    if _is_chitchat(user_message):
        return False
    text = (user_message or '').strip()
    if _WORLD_INTRO_PATTERN.search(text):
        return True
    if context and isinstance(context.intent_hint, dict):
        intent = str(context.intent_hint.get('intent') or '').strip().lower()
        if intent == 'verify_state':
            return True
    help_only = re.search(r'(?:怎么用|用法|语法|示例|\bhelp\b|\busage\b|\bexample\b)', text, flags=re.IGNORECASE)
    if help_only and not _WORLD_INTRO_PATTERN.search(text):
        return False
    if len(text) >= 4 and not _is_chitchat(text):
        return True
    return False


def assess_draft_completeness(
    *,
    user_message: str,
    draft_text: str,
    tool_results: Sequence[ToolResult],
    config: AgentLoopConfig,
    reason_context: Optional[DraftReasonContext] = None,
) -> DraftCompletenessVerdict:
    draft = (draft_text or '').strip()
    has_grounding = has_successful_grounding_obs(tool_results)
    deferral = is_deferral_prose(draft, config=config)

    if deferral and not has_grounding:
        return DraftCompletenessVerdict.retry_loop
    if _needs_runtime_grounding(user_message, context=reason_context) and not has_grounding:
        if not draft or deferral:
            return DraftCompletenessVerdict.retry_loop
        if len(draft) < config.min_complete_chars:
            return DraftCompletenessVerdict.retry_loop
    if draft and len(draft) < config.min_complete_chars and _needs_runtime_grounding(user_message, context=reason_context):
        if not has_grounding:
            return DraftCompletenessVerdict.retry_loop
    if not draft and user_message.strip() and _needs_runtime_grounding(user_message, context=reason_context):
        return DraftCompletenessVerdict.retry_loop
    return DraftCompletenessVerdict.complete


def assess_draft_completeness_with_budget(
    *,
    user_message: str,
    draft_text: str,
    tool_results: Sequence[ToolResult],
    config: AgentLoopConfig,
    reason_context: Optional[DraftReasonContext] = None,
    rounds_remaining: int,
) -> DraftCompletenessVerdict:
    verdict = assess_draft_completeness(
        user_message=user_message,
        draft_text=draft_text,
        tool_results=tool_results,
        config=config,
        reason_context=reason_context,
    )
    if verdict == DraftCompletenessVerdict.retry_loop and rounds_remaining <= 0:
        return DraftCompletenessVerdict.fail_fallback
    return verdict


def is_draft_streamable(
    *,
    draft_text: str,
    tool_results: Sequence[ToolResult],
    user_message: str,
    config: AgentLoopConfig,
    reason_context: Optional[DraftReasonContext] = None,
) -> bool:
    draft = (draft_text or '').strip()
    if not draft:
        return False
    if is_deferral_prose(draft, config=config) and not has_successful_grounding_obs(tool_results):
        return False
    verdict = assess_draft_completeness(
        user_message=user_message,
        draft_text=draft_text,
        tool_results=tool_results,
        config=config,
        reason_context=reason_context,
    )
    return verdict == DraftCompletenessVerdict.complete
