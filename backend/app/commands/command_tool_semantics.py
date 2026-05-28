"""Command tool semantics declared at registration (registry SSOT)."""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional, Sequence, Tuple

InteractionProfile = Literal['read', 'mutate']
ManifestTier = Literal['informational', 'full', 'none']


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
    """Match args prefix (case-insensitive) to an effective interaction profile."""

    arg_prefix: Tuple[str, ...]
    interaction_profile: InteractionProfile
    invocation_guard: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class CommandToolSemantics:
    interaction_profile: InteractionProfile
    semantic_pending: bool = False
    subcommand_profiles: Tuple[SubcommandProfileRule, ...] = ()
    observation_message_mode: Optional[str] = None
    observation_data_keys: Optional[frozenset[str]] = None
    manifest_tier: ManifestTier = 'none'
    routing_hint: str = ''
    routing_hint_i18n: Dict[str, str] = field(default_factory=dict)
    invocation_guard: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.invocation_guard:
            object.__setattr__(self, 'invocation_guard', default_guard_for(self.interaction_profile))

    def to_dict(self) -> Dict[str, Any]:
        sub = [
            {
                'arg_prefix': list(rule.arg_prefix),
                'interaction_profile': rule.interaction_profile,
            }
            for rule in self.subcommand_profiles
        ]
        data_keys = sorted(self.observation_data_keys) if self.observation_data_keys else None
        return {
            'interaction_profile': self.interaction_profile,
            'semantic_pending': self.semantic_pending,
            'subcommand_profiles': sub,
            'observation_message_mode': self.observation_message_mode,
            'observation_data_keys': data_keys,
            'manifest_tier': self.manifest_tier,
            'routing_hint': self.routing_hint or None,
            'routing_hint_i18n': dict(self.routing_hint_i18n) if self.routing_hint_i18n else None,
        }


DEFAULT_READ_SEMANTICS = CommandToolSemantics(interaction_profile='read')
DEFAULT_MUTATE_SEMANTICS = CommandToolSemantics(interaction_profile='mutate')

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

INFORMATIONAL_MANIFEST = dataclasses.replace(DEFAULT_READ_SEMANTICS, manifest_tier='informational')

CREATE_MUTATE_SEMANTICS = CommandToolSemantics(
    interaction_profile='mutate',
    routing_hint='Example/syntax requests should use `help create`; call only with explicit execution intent and confirmation.',
    routing_hint_i18n={
        'zh-CN': 'create 会改变系统状态。示例/语法问题应使用 help create；仅在明确执行且确认后调用。',
        'en-US': 'create mutates system state. Example/syntax requests should use `help create`; call only with explicit execution intent and confirmation.',
    },
)

TASK_MUTATE_SEMANTICS = CommandToolSemantics(
    interaction_profile='mutate',
    subcommand_profiles=TASK_SUBCOMMAND_PROFILES,
    routing_hint='For task examples/syntax/usage, route to `help task` (or primer) first; call state-changing subcommands only after explicit execution intent and confirmation.',
    routing_hint_i18n={
        'zh-CN': '若用户问 task 的例子/语法/用法，先走 help task（或 primer）；不要把示例请求当作执行请求。仅在用户明确执行且确认后才可调用会改状态的 task 子命令。',
        'en-US': 'For task examples/syntax/usage, route to `help task` (or primer) first; do not treat example requests as execute intent. Call state-changing task subcommands only after explicit execution intent and confirmation.',
    },
)

WORLD_MUTATE_SEMANTICS = CommandToolSemantics(
    interaction_profile='mutate',
    subcommand_profiles=WORLD_SUBCOMMAND_PROFILES,
)

NOTICE_MUTATE_SEMANTICS = CommandToolSemantics(
    interaction_profile='mutate',
    subcommand_profiles=NOTICE_SUBCOMMAND_PROFILES,
)

AGENT_READ_SEMANTICS = CommandToolSemantics(
    interaction_profile='read',
    subcommand_profiles=AGENT_SUBCOMMAND_PROFILES,
    manifest_tier='informational',
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
    """Resolve semantics from registry ClassVar only (no command-name frozensets)."""
    from app.commands.registry import command_registry

    name = str(command_name or '').strip().lower()
    cmd = command_registry.get_command(name)
    if cmd is None:
        return CommandToolSemantics(interaction_profile='read', semantic_pending=True)
    base = getattr(type(cmd), 'tool_semantics', DEFAULT_READ_SEMANTICS)
    if not args or not base.subcommand_profiles:
        return base
    matched = _match_subcommand_rule(base.subcommand_profiles, args)
    if matched is None:
        return base
    guard = matched.invocation_guard if matched.invocation_guard is not None else default_guard_for(matched.interaction_profile)
    return dataclasses.replace(
        base,
        interaction_profile=matched.interaction_profile,
        invocation_guard=dict(guard),
    )


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
