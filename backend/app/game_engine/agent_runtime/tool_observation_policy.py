"""ToolObservation policy for LLM context and trace previews."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional

DEFAULT_OBSERVATION_DATA_KEYS: FrozenSet[str] = frozenset({'ok', 'phase', 'handle', 'service_id'})
OBSERVATION_MESSAGE_MODES: FrozenSet[str] = frozenset({'full', 'summary', 'blocked'})


@dataclass(frozen=True)
class ToolObservationPolicy:
    message_mode: str = 'summary'
    max_message_chars: int = 4000
    trace_preview_chars: int = 400
    data_keys: FrozenSet[str] = DEFAULT_OBSERVATION_DATA_KEYS


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        out = int(value)
    except Exception:
        return default
    return out if out > 0 else default


def _default_policy_for_profile(profile: str) -> ToolObservationPolicy:
    if profile in {'document', 'read'}:
        return ToolObservationPolicy(message_mode='full')
    return ToolObservationPolicy(message_mode='summary')


def _policy_from_mapping(raw: Dict[str, Any], base: ToolObservationPolicy) -> ToolObservationPolicy:
    mode = str(raw.get('message_mode') or base.message_mode).strip().lower()
    if mode not in OBSERVATION_MESSAGE_MODES:
        mode = base.message_mode
    keys_raw = raw.get('data_keys')
    if isinstance(keys_raw, list):
        data_keys = frozenset((str(k).strip() for k in keys_raw if str(k).strip()))
    else:
        data_keys = base.data_keys
    return ToolObservationPolicy(
        message_mode=mode,
        max_message_chars=_coerce_positive_int(raw.get('max_message_chars'), base.max_message_chars),
        trace_preview_chars=_coerce_positive_int(raw.get('trace_preview_chars'), base.trace_preview_chars),
        data_keys=data_keys,
    )


def _command_ability_policy(session: Any, command_name: str) -> Optional[Dict[str, Any]]:
    if session is None:
        return None
    try:
        from app.models.graph import Node
        row = session.query(Node).filter(
            Node.type_code == 'system_command_ability',
            Node.attributes['command_name'].astext == command_name,
            Node.is_active == True,
        ).first()
        if row is None:
            return None
        attrs = row.attributes or {}
        raw = attrs.get('agent_observation_policy')
        return dict(raw) if isinstance(raw, dict) else None
    except Exception:
        return None


def resolve_tool_observation_policy(command_name: str, *, session: Any=None) -> ToolObservationPolicy:
    """Resolve policy from command ability override, then command semantics."""
    name = str(command_name or '').strip().lower()
    try:
        from app.commands.tool_semantics import get_command_tool_semantics
        sem = get_command_tool_semantics(name)
        profile = str(sem.get('interaction_profile') or '').strip().lower()
        semantic_pending = bool(sem.get('semantic_pending'))
    except Exception:
        profile = ''
        semantic_pending = True
    if semantic_pending:
        base = ToolObservationPolicy(message_mode='summary')
    else:
        base = _default_policy_for_profile(profile)
    raw = _command_ability_policy(session, name)
    if raw:
        return _policy_from_mapping(raw, base)
    return base


def first_non_empty_line(text: str) -> str:
    for line in (text or '').splitlines():
        s = line.strip()
        if s:
            return s
    return ''


def apply_observation_message_policy(message: str, policy: ToolObservationPolicy) -> str:
    """Return the message text allowed into ToolObservation."""
    raw = str(message or '')
    original_chars = len(raw)
    if policy.message_mode == 'blocked':
        msg = f'[message blocked by observation policy; original_chars={original_chars}]'
    elif policy.message_mode == 'summary':
        head = first_non_empty_line(raw)
        if head:
            msg = f'{head}\n[summary; original_chars={original_chars}]'
        else:
            msg = f'[summary; original_chars={original_chars}]'
    else:
        msg = raw
    if len(msg) > policy.max_message_chars:
        if policy.max_message_chars <= 3:
            msg = msg[:policy.max_message_chars]
        else:
            msg = msg[:policy.max_message_chars - 3] + '...'
    return msg


def trace_message_preview(message: str, policy: ToolObservationPolicy) -> str:
    """Return the trace preview using the same message policy as observations."""
    msg = apply_observation_message_policy(message, policy)
    limit = max(1, int(policy.trace_preview_chars))
    if len(msg) <= limit:
        return msg
    return msg[:limit] + '\n...[truncated]'
