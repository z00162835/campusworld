"""Runtime execution gate for caller policy + callee semantics.

Adapter contract: the external API and ``GateDecision`` structure are stable.
Internally, after the legacy caller/callee checks pass, the gate delegates
``side_effect_level`` / ``data_classification`` evaluation to the
``PolicyEngine`` (``before_tool_call`` check-point). The legacy reason_code set
is preserved; policy denials surface as ``guard_blocked_policy`` with the
detailed ``policy_decision`` written to the trace by the caller.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from app.commands.command_tool_semantics import resolve_command_tool_semantics
from app.game_engine.agent_runtime.policy import PolicyContext, PolicyDecision, PolicyEngine
from app.game_engine.agent_runtime.policy.check_points import CheckPoint
_PROFILE_RANK = {'read': 1, 'mutate': 2}
_EXECUTE_PATTERNS = ('\\b请执行\\b', '\\b确认执行\\b', '\\b继续执行\\b', '\\b马上创建\\b', '\\b帮我创建\\b', '\\byes,\\s*execute\\b', '\\bexecute now\\b')
_VERIFY_PATTERNS = ('\\b是否存在\\b', '\\b现在是什么状态\\b', '\\b查一下\\b', '\\bcurrent state\\b', '\\bdoes it exist\\b')
_INFO_PATTERNS = ('\\b例子\\b', '\\b怎么用\\b', '\\b语法\\b', '\\bhelp\\b', '\\bexample\\b', '\\busage\\b', '\\bsyntax\\b')

@dataclass(frozen=True)
class GateDecision:
    allow: bool
    reason_code: str
    intent: str
    effective_profile: str
    effective_guard: Dict[str, Any]
    caller_profile: str
    callee_profile: str

def _normalize_profile(value: Any) -> str:
    s = str(value or '').strip().lower()
    if s in _PROFILE_RANK:
        return s
    return 'read'

def min_privilege_profile(caller_profile: str, callee_profile: str) -> str:
    cp = _normalize_profile(caller_profile)
    tp = _normalize_profile(callee_profile)
    return cp if _PROFILE_RANK[cp] <= _PROFILE_RANK[tp] else tp

def _parse_caller_policy(context_metadata: Dict[str, Any]) -> Dict[str, Any]:
    raw = context_metadata.get('agent_invocation_policy')
    policy = raw if isinstance(raw, dict) else {}
    caller_profile = _normalize_profile(policy.get('profile') or policy.get('intent_ceiling') or context_metadata.get('agent_interaction_profile') or 'mutate')
    allow_mutate = bool(policy.get('allow_mutate', caller_profile == 'mutate'))
    require_confirm = bool(policy.get('require_confirmation_for_mutate', True))
    scopes = policy.get('allowed_side_effect_scopes')
    if not isinstance(scopes, list) or not scopes:
        scopes = ['none'] if caller_profile != 'mutate' else ['none', 'state_change']
    return {'caller_profile': caller_profile, 'allow_mutate': allow_mutate, 'require_confirmation_for_mutate': require_confirm, 'allowed_side_effect_scopes': [str(x) for x in scopes]}

def _parse_intent(user_message: str, args: List[str], meta: Dict[str, Any]) -> str:
    explicit = meta.get('agent_intent')
    if explicit in {'informational', 'verify_state', 'execute'}:
        return str(explicit)
    text = f"{user_message or ''} {' '.join(args or [])}".lower()
    for pat in _EXECUTE_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE):
            return 'execute'
    for pat in _VERIFY_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE):
            return 'verify_state'
    for pat in _INFO_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE):
            return 'informational'
    return 'informational'

def _is_confirmed(meta: Dict[str, Any], guard: Dict[str, Any], user_message: str) -> bool:
    if bool(meta.get('confirmed_execute') or meta.get('execution_confirmed')):
        return True
    phrases = guard.get('confirm_phrase_any')
    if not isinstance(phrases, list) or not phrases:
        phrases = ['请执行', '确认执行', '继续执行', 'yes, execute']
    msg = str(user_message or '')
    return any((str(p).strip() and str(p).strip().lower() in msg.lower() for p in phrases))

def _load_callee_semantics(db_session, command_name: str, args: List[str]) -> Dict[str, Any]:
    sem = resolve_command_tool_semantics(command_name, args=args)
    return {
        'interaction_profile': sem.interaction_profile,
        'semantic_pending': sem.semantic_pending,
        'invocation_guard': dict(sem.invocation_guard or {}),
        'side_effect_level': sem.side_effect_level,
        'data_classification': sem.data_classification,
        'tool_groups': tuple(sem.tool_groups or ()),
    }

def _effective_guard(caller_policy: Dict[str, Any], callee_guard: Dict[str, Any], effective_profile: str) -> Dict[str, Any]:
    caller_allowed = {'informational', 'verify_state'}
    if caller_policy.get('caller_profile') == 'mutate':
        caller_allowed.add('execute')
    callee_allowed_raw = callee_guard.get('allowed_intents')
    callee_allowed = {str(x) for x in callee_allowed_raw} if isinstance(callee_allowed_raw, list) and callee_allowed_raw else {'informational', 'verify_state', 'execute'}
    allowed_intents = sorted(caller_allowed.intersection(callee_allowed))
    side_scopes = {str(x) for x in caller_policy.get('allowed_side_effect_scopes') or ['none']}
    callee_scope = str(callee_guard.get('side_effect_scope') or 'none')
    eff_scope = callee_scope if callee_scope in side_scopes else 'none'
    require_confirm = bool(callee_guard.get('requires_confirmation', False)) or bool(caller_policy.get('require_confirmation_for_mutate', False))
    if effective_profile != 'mutate':
        require_confirm = False
    return {'allowed_intents': allowed_intents, 'side_effect_scope': eff_scope, 'requires_confirmation': require_confirm, 'block_when_intent_only_examples': bool(callee_guard.get('block_when_intent_only_examples', False))}

def evaluate_execution_gate(*, db_session, command_name: str, args: List[str], context_metadata: Optional[Dict[str, Any]]) -> GateDecision:
    meta = dict(context_metadata or {})
    caller = _parse_caller_policy(meta)
    callee_sem = _load_callee_semantics(db_session, command_name, args)
    callee_profile = _normalize_profile(callee_sem.get('interaction_profile'))
    callee_guard = dict(callee_sem.get('invocation_guard') or {})
    effective_profile = min_privilege_profile(caller['caller_profile'], callee_profile)
    effective_guard = _effective_guard(caller, callee_guard, effective_profile)
    user_message = str(meta.get('user_message') or '')
    intent = _parse_intent(user_message, args, meta)
    if effective_profile != callee_profile and callee_profile == 'mutate':
        return GateDecision(allow=False, reason_code='guard_blocked_profile_ceiling', intent=intent, effective_profile=effective_profile, effective_guard=effective_guard, caller_profile=caller['caller_profile'], callee_profile=callee_profile)
    if intent not in set(effective_guard.get('allowed_intents') or []):
        return GateDecision(allow=False, reason_code='guard_blocked_intent', intent=intent, effective_profile=effective_profile, effective_guard=effective_guard, caller_profile=caller['caller_profile'], callee_profile=callee_profile)
    if effective_guard.get('block_when_intent_only_examples') and intent == 'informational':
        return GateDecision(allow=False, reason_code='guard_blocked_intent', intent=intent, effective_profile=effective_profile, effective_guard=effective_guard, caller_profile=caller['caller_profile'], callee_profile=callee_profile)
    if effective_guard.get('side_effect_scope') != str(callee_guard.get('side_effect_scope') or 'none'):
        return GateDecision(allow=False, reason_code='guard_blocked_scope', intent=intent, effective_profile=effective_profile, effective_guard=effective_guard, caller_profile=caller['caller_profile'], callee_profile=callee_profile)
    if effective_guard.get('requires_confirmation') and (not _is_confirmed(meta, callee_guard, user_message)):
        return GateDecision(allow=False, reason_code='guard_blocked_confirmation', intent=intent, effective_profile=effective_profile, effective_guard=effective_guard, caller_profile=caller['caller_profile'], callee_profile=callee_profile)
    # Delegate side_effect_level / data_classification to PolicyEngine.
    policy_ctx = PolicyContext(
        check_point=CheckPoint.BEFORE_TOOL_CALL,
        command_name=command_name,
        command_args=tuple(args or []),
        interaction_profile=callee_profile,
        side_effect_level=str(callee_sem.get('side_effect_level') or 'none'),
        data_classification=callee_sem.get('data_classification'),
        tool_groups=tuple(callee_sem.get('tool_groups') or ()),
        user_message=user_message,
        caller_profile=caller['caller_profile'],
        active_skill_context=meta.get('active_skill_context'),
    )
    policy_decision = _policy_engine.evaluate(policy_ctx)
    if policy_decision.is_block:
        effective_guard_with_policy = dict(effective_guard)
        effective_guard_with_policy['policy_decision'] = _policy_decision_to_trace(policy_decision)
        return GateDecision(allow=False, reason_code='guard_blocked_policy', intent=intent, effective_profile=effective_profile, effective_guard=effective_guard_with_policy, caller_profile=caller['caller_profile'], callee_profile=callee_profile)
    return GateDecision(allow=True, reason_code='guard_pass', intent=intent, effective_profile=effective_profile, effective_guard=effective_guard, caller_profile=caller['caller_profile'], callee_profile=callee_profile)

def _policy_decision_to_trace(decision: PolicyDecision) -> Dict[str, Any]:
    evidence = decision.evidence or {}
    return {
        'step': 'policy_decision',
        'check_point': decision.check_point,
        'decision': decision.decision,
        'reason_code': decision.reason_code,
        'detector': evidence.get('detector'),
        'runtime_action': decision.runtime_action,
        'evidence': evidence,
    }


# Module-level engine; detectors are stateless so reuse is safe.
_policy_engine = PolicyEngine()

def guard_error_message(command_name: str, reason_code: str) -> str:
    if reason_code == 'guard_blocked_profile_ceiling':
        return f'Blocked by caller policy ceiling for `{command_name}`. Use `help {command_name}` or `primer commands` for examples.'
    if reason_code == 'guard_blocked_confirmation':
        return f'`{command_name}` requires explicit confirmation before execution. Use `help {command_name}` for usage details.'
    if reason_code == 'guard_blocked_scope':
        return f'`{command_name}` side effect scope is not allowed by caller policy. Use `help {command_name}` for non-mutating guidance.'
    if reason_code == 'guard_blocked_policy':
        return f'`{command_name}` was blocked by behaviour policy. Use `help {command_name}` or `primer commands` for non-mutating alternatives.'
    return f'`{command_name}` was blocked by execution guard due to intent mismatch. Use `help {command_name}` or `primer commands`.'
