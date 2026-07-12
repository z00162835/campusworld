"""Command tool semantics declared at registration (registry SSOT)."""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

InteractionProfile = Literal['read', 'mutate']
ManifestTier = Literal['informational', 'full', 'none']
ToolSideEffectLevel = Literal['none', 'read', 'write_low', 'write_high']
ToolDataClassification = Literal['public', 'internal', 'confidential', 'restricted']

PLATFORM_ERROR_CODES: frozenset[str] = frozenset({
    'INVALID_PARAM', 'NOT_FOUND', 'TIMEOUT', 'SERVICE_ERROR',
    'RATE_LIMIT', 'PERMISSION_DENIED', 'POLICY_DENIED',
    'CONFLICT', 'NOT_AVAILABLE',
})


def default_guard_for(profile: InteractionProfile) -> Dict[str, Any]:
    if profile == 'mutate':
        return {
            'requires_confirmation': True,
            'allowed_intents': ['execute'],
            'block_when_intent_only_examples': True,
            'side_effect_scope': 'state_change',
        }
    return {
        'requires_confirmation': False,
        'allowed_intents': ['verify_state', 'informational'],
        'block_when_intent_only_examples': False,
        'side_effect_scope': 'none',
    }


@dataclass(frozen=True)
class SubcommandProfileRule:
    """Match args prefix (case-insensitive) to an effective interaction profile and tool groups."""

    arg_prefix: Tuple[str, ...]
    interaction_profile: InteractionProfile
    invocation_guard: Optional[Dict[str, Any]] = None
    tool_groups: Tuple[str, ...] = ()


@dataclass(frozen=True)
class CommandToolSemantics:
    interaction_profile: InteractionProfile
    semantic_pending: bool = False
    subcommand_profiles: Tuple[SubcommandProfileRule, ...] = ()
    # When non-None and the command is invoked with no args, resolve the bare
    # form to this profile instead of the class-level interaction_profile. Use
    # case: `task` is class-level `mutate` but `task` with no args only prints
    # usage (no state change), so it should be treated as `read` to avoid the
    # execution_gate blocking informational intent on the bare call.
    default_profile_when_no_subcommand: Optional[InteractionProfile] = None
    observation_message_mode: Optional[str] = None
    observation_data_keys: Optional[frozenset[str]] = None
    manifest_tier: ManifestTier = 'none'
    routing_hint: str = ''
    routing_hint_i18n: Dict[str, str] = field(default_factory=dict)
    invocation_guard: Dict[str, Any] = field(default_factory=dict)
    side_effect_level: Optional[ToolSideEffectLevel] = None
    idempotent: bool = False
    deterministic: bool = False
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    error_schema: Optional[Dict[str, Any]] = None
    data_classification: Optional[ToolDataClassification] = None
    data_scope: Tuple[str, ...] = ()
    # Refined behavior groups for F16 PolicyEngine skill_tool_group detector.
    # Empty tuple means "derive from the resolved interaction_profile" (read or mutate).
    tool_groups: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.invocation_guard:
            object.__setattr__(self, 'invocation_guard', default_guard_for(self.interaction_profile))

    def to_dict(self) -> Dict[str, Any]:
        sub = [
            {
                'arg_prefix': list(rule.arg_prefix),
                'interaction_profile': rule.interaction_profile,
                'tool_groups': list(rule.tool_groups) if rule.tool_groups else None,
            }
            for rule in self.subcommand_profiles
        ]
        data_keys = sorted(self.observation_data_keys) if self.observation_data_keys else None
        return {
            'interaction_profile': self.interaction_profile,
            'semantic_pending': self.semantic_pending,
            'subcommand_profiles': sub,
            'default_profile_when_no_subcommand': self.default_profile_when_no_subcommand,
            'observation_message_mode': self.observation_message_mode,
            'observation_data_keys': data_keys,
            'manifest_tier': self.manifest_tier,
            'routing_hint': self.routing_hint or None,
            'routing_hint_i18n': dict(self.routing_hint_i18n) if self.routing_hint_i18n else None,
            'side_effect_level': self.side_effect_level,
            'idempotent': self.idempotent,
            'deterministic': self.deterministic,
            'input_schema': self.input_schema,
            'output_schema': self.output_schema,
            'error_schema': self.error_schema,
            'data_classification': self.data_classification,
            'data_scope': list(self.data_scope) if self.data_scope else None,
            'tool_groups': list(self.tool_groups) if self.tool_groups else None,
        }


def build_error_schema(codes: Tuple[str, ...]) -> Dict[str, Any]:
    """Build a JSON Schema for command errors using platform-unified codes.

    The localized message for each code is resolved at presentation time via
    the i18n key ``command.error.<code>`` (existing i18n/command_resource pipeline).
    """
    unknown = [c for c in codes if c not in PLATFORM_ERROR_CODES]
    if unknown:
        raise ValueError(f'unknown platform error codes: {unknown}')
    return {
        'type': 'object',
        'required': ['code', 'message'],
        'properties': {
            'code': {'type': 'string', 'enum': list(codes)},
            'message': {'type': 'string'},
            'retryable': {'type': 'boolean'},
        },
    }


def resolve_side_effect_level(sem: 'CommandToolSemantics') -> 'ToolSideEffectLevel':
    """Hybrid: explicit declaration wins; else derive from interaction_profile + invocation_guard."""
    if sem.side_effect_level is not None:
        return sem.side_effect_level
    if sem.interaction_profile == 'read':
        return 'read'
    # mutate branch
    guard = sem.invocation_guard or {}
    if bool(guard.get('requires_confirmation', True)):
        return 'write_high'
    return 'write_low'


def validate_data_scope(scope: Tuple[str, ...]) -> List[str]:
    """Return any type_codes in ``scope`` not registered in the graph ontology.

    An empty list means every entry is a known ``NodeType.type_code``. When the
    database is unavailable, returns an empty list so callers can audit
    separately rather than blocking on infrastructure failures.
    """
    if not scope:
        return []
    from app.models.graph import NodeType
    from app.core.database import db_session_context
    try:
        with db_session_context() as session:
            known = {row[0] for row in session.query(NodeType.type_code).all()}
    except Exception:
        return []
    return [s for s in scope if s not in known]


DEFAULT_READ_SEMANTICS = CommandToolSemantics(interaction_profile='read')

READ_SUBCOMMAND = lambda *prefix: SubcommandProfileRule(arg_prefix=prefix, interaction_profile='read')
MUTATE_SUBCOMMAND = lambda *prefix: SubcommandProfileRule(arg_prefix=prefix, interaction_profile='mutate')

TASK_SUBCOMMAND_PROFILES = (
    READ_SUBCOMMAND('list'),
    READ_SUBCOMMAND('show'),
)

WORLD_SUBCOMMAND_PROFILES = (
    READ_SUBCOMMAND('list'),
    READ_SUBCOMMAND('status'),
    READ_SUBCOMMAND('validate'),
    READ_SUBCOMMAND('bridge', 'list'),
    READ_SUBCOMMAND('bridge', 'validate'),
    READ_SUBCOMMAND('content', 'validate'),
    READ_SUBCOMMAND('content', 'diff'),
)

NOTICE_SUBCOMMAND_PROFILES = (
    READ_SUBCOMMAND('list'),
    READ_SUBCOMMAND('view'),
)

AGENT_SUBCOMMAND_PROFILES = (
    READ_SUBCOMMAND('list'),
    READ_SUBCOMMAND('show'),
    READ_SUBCOMMAND('status'),
    READ_SUBCOMMAND('tool'),
    MUTATE_SUBCOMMAND('tool', 'add'),
    MUTATE_SUBCOMMAND('tool', 'del'),
)

TASK_MUTATE_SEMANTICS = CommandToolSemantics(
    interaction_profile='mutate',
    subcommand_profiles=TASK_SUBCOMMAND_PROFILES,
    default_profile_when_no_subcommand='read',
    routing_hint='For task examples/syntax/usage, route to `help task` (or primer) first; call state-changing subcommands only after explicit execution intent and confirmation.',
    routing_hint_i18n={
        'zh-CN': '若用户问 task 的例子/语法/用法，先走 help task（或 primer）；不要把示例请求当作执行请求。仅在用户明确执行且确认后才可调用会改状态的 task 子命令。',
        'en-US': 'For task examples/syntax/usage, route to `help task` (or primer) first; do not treat example requests as execute intent. Call state-changing task subcommands only after explicit execution intent and confirmation.',
    },
)


def _normalize_args(args: Sequence[str]) -> Tuple[str, ...]:
    return tuple((str(a).strip().lower() for a in args if str(a).strip()))


def _match_subcommand_rule(
    rules: Tuple[SubcommandProfileRule, ...],
    args: Sequence[str],
) -> Optional[SubcommandProfileRule]:
    tokens = _normalize_args(args)
    if not tokens or not rules:
        return None
    best: Optional[SubcommandProfileRule] = None
    best_len = -1
    for rule in rules:
        prefix = _normalize_args(rule.arg_prefix)
        if not prefix:
            continue
        if len(tokens) < len(prefix):
            continue
        if tokens[: len(prefix)] != prefix:
            continue
        if len(prefix) > best_len:
            best = rule
            best_len = len(prefix)
    return best


def resolve_command_tool_semantics(
    command_name: str,
    args: Optional[Sequence[str]] = None,
) -> CommandToolSemantics:
    """Resolve semantics from registry ClassVar only (no command-name frozensets).

    When the resolved semantics leaves ``side_effect_level`` unset (None), the
    effective level is derived from the interaction profile and invocation
    guard so callers observe a concrete side-effect contract without having to
    invoke ``resolve_side_effect_level`` separately.
    """
    from app.commands.registry import command_registry

    name = str(command_name or '').strip().lower()
    cmd = command_registry.get_command(name)
    if cmd is None:
        return CommandToolSemantics(interaction_profile='read', semantic_pending=True, tool_groups=('read',))
    base = getattr(type(cmd), 'tool_semantics', DEFAULT_READ_SEMANTICS)
    if not args or not base.subcommand_profiles:
        resolved = base
        # A command that exposes subcommands may declare a safer profile for the
        # bare (no-arg) form: e.g. `task` with no args only prints usage and
        # should not be treated as the class-level `mutate`, otherwise the
        # execution_gate blocks informational intent on the bare call. This
        # fallback triggers ONLY for an explicit empty arg list (``args=[]``,
        # the execution_gate path); when ``args is None`` (manifest grouping /
        # classification) the class-level profile is preserved so a mutate
        # command is still grouped under state-changing tools.
        if args is not None and len(args) == 0 and base.subcommand_profiles and base.default_profile_when_no_subcommand:
            prof = base.default_profile_when_no_subcommand
            resolved = dataclasses.replace(
                base,
                interaction_profile=prof,
                invocation_guard=dict(default_guard_for(prof)),
                tool_groups=base.tool_groups or (prof,),
            )
    else:
        matched = _match_subcommand_rule(base.subcommand_profiles, args)
        if matched is None:
            resolved = base
        else:
            guard = matched.invocation_guard if matched.invocation_guard is not None else default_guard_for(matched.interaction_profile)
            tool_groups = matched.tool_groups if matched.tool_groups else (matched.interaction_profile,)
            resolved = dataclasses.replace(
                base,
                interaction_profile=matched.interaction_profile,
                invocation_guard=dict(guard),
                tool_groups=tool_groups,
            )
    if resolved.side_effect_level is None:
        resolved = dataclasses.replace(resolved, side_effect_level=resolve_side_effect_level(resolved))
    if not resolved.tool_groups:
        resolved = dataclasses.replace(resolved, tool_groups=(resolved.interaction_profile,))
    return resolved


def get_command_tool_semantics(
    command_name: str,
    args: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Legacy dict shape for callers that expect mapping semantics."""
    sem = resolve_command_tool_semantics(command_name, args=args)
    out = sem.to_dict()
    out['invocation_guard'] = dict(sem.invocation_guard)
    return out


def pick_routing_hint(attrs: Dict[str, Any], locale: str) -> Optional[str]:
    raw_i18n = attrs.get('routing_hint_i18n')
    if isinstance(raw_i18n, dict):
        if locale in raw_i18n and str(raw_i18n.get(locale) or '').strip():
            return str(raw_i18n[locale]).strip()
        if str(raw_i18n.get('en-US') or '').strip():
            return str(raw_i18n['en-US']).strip()
    raw = attrs.get('routing_hint')
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None
