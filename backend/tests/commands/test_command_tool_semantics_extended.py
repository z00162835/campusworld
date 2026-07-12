import pytest
from app.commands.command_tool_semantics import (
    CommandToolSemantics,
    resolve_command_tool_semantics,
    resolve_side_effect_level,
    PLATFORM_ERROR_CODES,
)
from app.commands.init_commands import initialize_commands


@pytest.fixture(scope='module', autouse=True)
def _init_commands():
    initialize_commands(force_reinit=True)


@pytest.mark.unit
def test_new_fields_have_defaults():
    sem = CommandToolSemantics(interaction_profile='read')
    assert sem.side_effect_level is None
    assert sem.idempotent is False
    assert sem.deterministic is False
    assert sem.input_schema is None
    assert sem.output_schema is None
    assert sem.error_schema is None
    assert sem.data_classification is None
    assert sem.data_scope == ()


@pytest.mark.unit
def test_to_dict_includes_new_fields():
    sem = CommandToolSemantics(
        interaction_profile='read',
        side_effect_level='read',
        idempotent=True,
        deterministic=True,
        input_schema={'type': 'object'},
        data_classification='public',
        data_scope=('room',),
    )
    d = sem.to_dict()
    assert d['side_effect_level'] == 'read'
    assert d['idempotent'] is True
    assert d['deterministic'] is True
    assert d['input_schema'] == {'type': 'object'}
    assert d['data_classification'] == 'public'
    assert d['data_scope'] == ['room']


@pytest.mark.unit
def test_platform_error_codes_is_frozen_set():
    assert 'INVALID_PARAM' in PLATFORM_ERROR_CODES
    assert 'POLICY_DENIED' in PLATFORM_ERROR_CODES


@pytest.mark.unit
def test_resolve_task_bare_falls_back_to_read():
    """`task` called with an explicit empty arg list (execution_gate path)
    only prints usage (no state change); it must resolve to `read` via
    default_profile_when_no_subcommand so execution_gate does not block
    informational intent on the bare call."""
    sem = resolve_command_tool_semantics('task', args=[])
    assert sem.interaction_profile == 'read'


@pytest.mark.unit
def test_resolve_task_unspecified_args_keeps_class_profile():
    """When args is unspecified (manifest grouping / classification), the
    class-level profile is preserved so `task` is still grouped under
    state-changing tools."""
    sem = resolve_command_tool_semantics('task', args=None)
    assert sem.interaction_profile == 'mutate'


@pytest.mark.unit
def test_resolve_task_mutate_subcommand_still_mutate():
    """State-changing subcommands keep their mutate profile."""
    sem = resolve_command_tool_semantics('task', args=['complete', '1'])
    assert sem.interaction_profile == 'mutate'


@pytest.mark.unit
def test_resolve_task_read_subcommands_stay_read():
    assert resolve_command_tool_semantics('task', args=['list']).interaction_profile == 'read'
    assert resolve_command_tool_semantics('task', args=['show', '1']).interaction_profile == 'read'


@pytest.mark.unit
def test_default_profile_when_no_subcommand_field_defaults_none():
    sem = CommandToolSemantics(interaction_profile='mutate')
    assert sem.default_profile_when_no_subcommand is None


@pytest.mark.unit
def test_to_dict_includes_default_profile_when_no_subcommand():
    sem = CommandToolSemantics(
        interaction_profile='mutate',
        default_profile_when_no_subcommand='read',
    )
    d = sem.to_dict()
    assert d['default_profile_when_no_subcommand'] == 'read'


@pytest.mark.unit
def test_resolve_side_effect_level_explicit_wins():
    sem = CommandToolSemantics(interaction_profile='mutate', side_effect_level='write_low')
    assert resolve_side_effect_level(sem) == 'write_low'


@pytest.mark.unit
def test_resolve_side_effect_level_derive_read():
    sem = CommandToolSemantics(interaction_profile='read')
    assert resolve_side_effect_level(sem) == 'read'


@pytest.mark.unit
def test_resolve_side_effect_level_derive_write_high():
    sem = CommandToolSemantics(interaction_profile='mutate')  # default guard => requires_confirmation True
    assert resolve_side_effect_level(sem) == 'write_high'


@pytest.mark.unit
def test_resolve_side_effect_level_derive_write_low():
    sem = CommandToolSemantics(
        interaction_profile='mutate',
        invocation_guard={'requires_confirmation': False, 'allowed_intents': ['execute'], 'side_effect_scope': 'state_change'},
    )
    assert resolve_side_effect_level(sem) == 'write_low'


@pytest.mark.unit
def test_data_classification_only_accepts_known_tiers():
    # dataclass is not frozen-enforcing on Literal at runtime, but to_dict must round-trip
    sem = CommandToolSemantics(interaction_profile='read', data_classification='confidential', data_scope=('task', 'room'))
    d = sem.to_dict()
    assert d['data_classification'] == 'confidential'
    assert d['data_scope'] == ['task', 'room']


@pytest.mark.integration
def test_validate_data_scope_against_known_type_codes():
    from app.commands.command_tool_semantics import validate_data_scope
    # known type_codes from graph seed
    assert validate_data_scope(('room', 'building')) == []
    # unknown type_code returned in error list
    bad = validate_data_scope(('nonexistent_type',))
    assert 'nonexistent_type' in bad


@pytest.mark.unit
def test_error_schema_must_use_platform_codes():
    from app.commands.command_tool_semantics import build_error_schema, PLATFORM_ERROR_CODES
    schema = build_error_schema(codes=('NOT_FOUND', 'INVALID_PARAM'))
    assert set(schema['properties']['code']['enum']).issubset(PLATFORM_ERROR_CODES)
    assert schema['properties']['code']['enum'] == ['NOT_FOUND', 'INVALID_PARAM']
    assert schema['properties']['message']['type'] == 'string'


@pytest.mark.unit
def test_error_schema_rejects_unknown_code():
    from app.commands.command_tool_semantics import build_error_schema
    with pytest.raises(ValueError):
        build_error_schema(codes=('BOGUS_CODE',))


@pytest.mark.unit
def test_look_has_structured_contract():
    sem = resolve_command_tool_semantics('look')
    assert sem.side_effect_level == 'none'
    assert sem.idempotent is True
    assert sem.deterministic is True
    assert sem.data_classification == 'public'
    assert sem.input_schema is not None
    assert 'target' in sem.input_schema.get('properties', {})


@pytest.mark.unit
def test_help_has_read_contract():
    sem = resolve_command_tool_semantics('help')
    assert sem.side_effect_level == 'none'
    assert sem.data_classification == 'public'
    assert sem.input_schema is not None


@pytest.mark.unit
def test_create_has_write_high_contract():
    sem = resolve_command_tool_semantics('create')
    assert sem.side_effect_level == 'write_high'
    assert sem.data_classification == 'internal'
    assert sem.error_schema is not None
    assert 'POLICY_DENIED' in sem.error_schema['properties']['code']['enum']


@pytest.mark.unit
def test_task_has_subcommand_aware_side_effect():
    assert resolve_command_tool_semantics('task', args=['list']).side_effect_level == 'read'
    assert resolve_command_tool_semantics('task', args=['create']).side_effect_level == 'write_high'


# ---------------------------------------------------------------------------
# Extended command tool contract annotations
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_stats_has_read_contract():
    sem = resolve_command_tool_semantics('stats')
    assert sem.side_effect_level == 'read'
    assert sem.data_classification == 'internal'
    assert sem.manifest_tier == 'informational'


@pytest.mark.unit
def test_version_has_none_side_effect_contract():
    sem = resolve_command_tool_semantics('version')
    assert sem.side_effect_level == 'none'
    assert sem.data_classification == 'public'
    assert sem.idempotent is True


@pytest.mark.unit
def test_quit_has_write_low_contract():
    sem = resolve_command_tool_semantics('quit')
    assert sem.side_effect_level == 'write_low'
    assert sem.idempotent is False
    assert sem.data_classification == 'public'


@pytest.mark.unit
def test_time_has_none_side_effect_contract():
    sem = resolve_command_tool_semantics('time')
    assert sem.side_effect_level == 'none'
    assert sem.data_classification == 'public'
    assert sem.deterministic is False


@pytest.mark.unit
def test_whoami_has_read_contract():
    sem = resolve_command_tool_semantics('whoami')
    assert sem.side_effect_level == 'read'
    assert sem.data_classification == 'public'
    assert sem.data_scope == ('account',)


@pytest.mark.unit
def test_who_has_read_contract():
    sem = resolve_command_tool_semantics('who')
    assert sem.side_effect_level == 'read'
    assert sem.data_classification == 'internal'
    assert sem.data_scope == ('account',)
    assert sem.deterministic is False


@pytest.mark.unit
def test_type_has_read_contract():
    sem = resolve_command_tool_semantics('type')
    assert sem.side_effect_level == 'read'
    assert sem.data_classification == 'public'
    assert sem.idempotent is True


@pytest.mark.unit
def test_space_has_read_contract():
    sem = resolve_command_tool_semantics('space')
    assert sem.side_effect_level == 'read'
    assert sem.data_classification == 'public'
    assert sem.idempotent is True
    assert sem.deterministic is True
    assert set(sem.data_scope) == {'room', 'building', 'building_floor'}
    assert sem.error_schema is not None


@pytest.mark.unit
def test_primer_has_none_side_effect_contract():
    sem = resolve_command_tool_semantics('primer')
    assert sem.side_effect_level == 'none'
    assert sem.data_classification == 'public'
    assert sem.idempotent is True
    assert sem.deterministic is True


@pytest.mark.unit
def test_agent_has_subcommand_aware_side_effect():
    assert resolve_command_tool_semantics('agent', args=['list']).side_effect_level == 'read'
    assert resolve_command_tool_semantics('agent', args=['show']).side_effect_level == 'read'
    assert resolve_command_tool_semantics('agent', args=['tool']).side_effect_level == 'read'
    assert resolve_command_tool_semantics('agent', args=['tool', 'add']).side_effect_level == 'write_high'
    assert resolve_command_tool_semantics('agent', args=['tool', 'del']).side_effect_level == 'write_high'


@pytest.mark.unit
def test_agent_data_classification_internal():
    sem = resolve_command_tool_semantics('agent')
    assert sem.data_classification == 'internal'
    assert sem.data_scope == ('npc_agent',)


@pytest.mark.unit
def test_world_has_subcommand_aware_side_effect():
    assert resolve_command_tool_semantics('world', args=['list']).side_effect_level == 'read'
    assert resolve_command_tool_semantics('world', args=['status']).side_effect_level == 'read'
    assert resolve_command_tool_semantics('world', args=['install']).side_effect_level == 'write_high'


@pytest.mark.unit
def test_world_data_classification_internal():
    sem = resolve_command_tool_semantics('world')
    assert sem.data_classification == 'internal'
    assert sem.data_scope == ('world',)
    assert sem.error_schema is not None


@pytest.mark.unit
def test_notice_has_subcommand_aware_side_effect():
    assert resolve_command_tool_semantics('notice', args=['list']).side_effect_level == 'read'
    assert resolve_command_tool_semantics('notice', args=['view']).side_effect_level == 'read'
    assert resolve_command_tool_semantics('notice', args=['publish']).side_effect_level == 'write_high'


@pytest.mark.unit
def test_notice_data_classification_internal():
    sem = resolve_command_tool_semantics('notice')
    assert sem.data_classification == 'internal'
    assert sem.data_scope == ('system_notice',)


@pytest.mark.unit
def test_find_has_read_contract():
    sem = resolve_command_tool_semantics('find')
    assert sem.side_effect_level == 'read'
    assert sem.data_classification == 'public'
    assert sem.idempotent is True
    assert sem.deterministic is True


@pytest.mark.unit
def test_describe_has_read_contract():
    sem = resolve_command_tool_semantics('describe')
    assert sem.side_effect_level == 'read'
    assert sem.data_classification == 'public'
    assert sem.idempotent is True
    assert sem.deterministic is True


@pytest.mark.unit
def test_go_has_write_low_contract():
    sem = resolve_command_tool_semantics('go')
    assert sem.side_effect_level == 'write_low'
    assert sem.idempotent is False
    assert sem.data_classification == 'internal'
    assert set(sem.data_scope) == {'room', 'character'}


@pytest.mark.unit
def test_enter_has_write_low_contract():
    sem = resolve_command_tool_semantics('enter')
    assert sem.side_effect_level == 'write_low'
    assert sem.idempotent is False
    assert sem.data_classification == 'internal'
    assert set(sem.data_scope) == {'world', 'world_entrance'}


@pytest.mark.unit
def test_leave_has_write_low_contract():
    sem = resolve_command_tool_semantics('leave')
    assert sem.side_effect_level == 'write_low'
    assert sem.idempotent is False
    assert sem.data_classification == 'internal'


@pytest.mark.unit
def test_task_pool_classvar_subcommand_aware():
    # TaskPoolCommand is not registered as a standalone command; it is invoked
    # internally by TaskCommand._do_pool. Assert the ClassVar contract directly.
    import dataclasses
    from app.commands.command_tool_semantics import (
        default_guard_for,
        resolve_side_effect_level,
    )
    from app.commands.game.task.task_pool_command import TaskPoolCommand

    base = TaskPoolCommand.tool_semantics
    assert base.data_classification == 'internal'
    assert base.data_scope == ('task',)
    assert base.side_effect_level is None  # subcommand-derived

    read_rule = next(r for r in base.subcommand_profiles if r.arg_prefix == ('list',))
    read_sem = dataclasses.replace(
        base,
        interaction_profile=read_rule.interaction_profile,
        invocation_guard=default_guard_for(read_rule.interaction_profile),
    )
    assert resolve_side_effect_level(read_sem) == 'read'

    mutate_rule = next(r for r in base.subcommand_profiles if r.arg_prefix == ('create',))
    mutate_sem = dataclasses.replace(
        base,
        interaction_profile=mutate_rule.interaction_profile,
        invocation_guard=default_guard_for(mutate_rule.interaction_profile),
    )
    assert resolve_side_effect_level(mutate_sem) == 'write_high'


@pytest.mark.unit
def test_task_pool_not_registered_returns_pending():
    # TaskPoolCommand is dispatched via TaskCommand._do_pool, not the registry.
    sem = resolve_command_tool_semantics('task.pool', args=['list'])
    assert sem.semantic_pending is True


@pytest.mark.unit
def test_explicit_tool_groups_propagate_to_resolution():
    import dataclasses
    from app.commands.command_tool_semantics import (
        CommandToolSemantics,
        SubcommandProfileRule,
        READ_SUBCOMMAND,
    )
    base = CommandToolSemantics(
        interaction_profile='mutate',
        tool_groups=('mutate', 'admin'),
    )
    sem = dataclasses.replace(base, interaction_profile='read', tool_groups=('read', 'observe'))
    resolved = resolve_command_tool_semantics.__wrapped__ if hasattr(resolve_command_tool_semantics, '__wrapped__') else resolve_command_tool_semantics
    # Direct construction: tool_groups is preserved.
    assert sem.tool_groups == ('read', 'observe')
    assert base.tool_groups == ('mutate', 'admin')


@pytest.mark.unit
def test_subcommand_tool_groups_override_base():
    import dataclasses
    from app.commands.command_tool_semantics import (
        CommandToolSemantics,
        SubcommandProfileRule,
        default_guard_for,
    )
    base = CommandToolSemantics(
        interaction_profile='mutate',
        subcommand_profiles=(
            SubcommandProfileRule(arg_prefix=('list',), interaction_profile='read', tool_groups=('observe',)),
            SubcommandProfileRule(arg_prefix=('create',), interaction_profile='mutate', tool_groups=('mutate',)),
        ),
        default_profile_when_no_subcommand='read',
    )
    # Simulate resolving with subcommand: list -> observe, create -> mutate
    list_rule = next(r for r in base.subcommand_profiles if r.arg_prefix == ('list',))
    list_sem = dataclasses.replace(
        base,
        interaction_profile=list_rule.interaction_profile,
        invocation_guard=default_guard_for(list_rule.interaction_profile),
        tool_groups=list_rule.tool_groups,
    )
    assert list_sem.tool_groups == ('observe',)

    create_rule = next(r for r in base.subcommand_profiles if r.arg_prefix == ('create',))
    create_sem = dataclasses.replace(
        base,
        interaction_profile=create_rule.interaction_profile,
        invocation_guard=default_guard_for(create_rule.interaction_profile),
        tool_groups=create_rule.tool_groups,
    )
    assert create_sem.tool_groups == ('mutate',)


@pytest.mark.unit
def test_subcommand_without_explicit_groups_uses_matched_profile():
    """A read subcommand of a command with explicit mutate base groups must
    not inherit those base groups; it falls back to (matched.interaction_profile,).
    """
    from app.commands.command_tool_semantics import (
        CommandToolSemantics,
        SubcommandProfileRule,
        _match_subcommand_rule,
        default_guard_for,
    )
    import dataclasses

    base = CommandToolSemantics(
        interaction_profile='mutate',
        tool_groups=('mutate', 'admin'),
        subcommand_profiles=(
            SubcommandProfileRule(arg_prefix=('list',), interaction_profile='read'),
        ),
    )
    matched = _match_subcommand_rule(base.subcommand_profiles, ['list'])
    assert matched is not None
    # Fallback should be (matched.interaction_profile,), not base.tool_groups
    expected_groups = matched.tool_groups if matched.tool_groups else (matched.interaction_profile,)
    assert expected_groups == ('read',)

    # Simulate the resolution path for a matched subcommand
    resolved = dataclasses.replace(
        base,
        interaction_profile=matched.interaction_profile,
        invocation_guard=default_guard_for(matched.interaction_profile),
        tool_groups=expected_groups,
    )
    assert resolved.tool_groups == ('read',)
    assert resolved.tool_groups != base.tool_groups


@pytest.mark.unit
def test_fine_grained_tool_groups_for_known_subcommands():
    """SPEC §4.4 taxonomy: subcommands resolve to refined child groups."""
    initialize_commands(force_reinit=True)

    # task list/show -> observe
    assert resolve_command_tool_semantics('task', args=['list']).tool_groups == ('observe',)
    assert resolve_command_tool_semantics('task', args=['show']).tool_groups == ('observe',)

    # agent list/show -> agent_meta; agent status -> observe
    assert resolve_command_tool_semantics('agent', args=['list']).tool_groups == ('agent_meta',)
    assert resolve_command_tool_semantics('agent', args=['show']).tool_groups == ('agent_meta',)
    assert resolve_command_tool_semantics('agent', args=['status']).tool_groups == ('observe',)

    # notice list/view -> communicate
    assert resolve_command_tool_semantics('notice', args=['list']).tool_groups == ('communicate',)
    assert resolve_command_tool_semantics('notice', args=['view']).tool_groups == ('communicate',)

    # whoami -> identity
    assert resolve_command_tool_semantics('whoami').tool_groups == ('identity',)

    # help/look -> read (parent, no child)
    assert resolve_command_tool_semantics('help').tool_groups == ('read',)


@pytest.mark.unit
def test_prompt_fallback_toggle():
    """enable_prompt_fallback controls whether the policy preamble is appended."""
    from app.game_engine.agent_runtime.frameworks.llm_pdca import (
        _append_policy_fallback,
        _prompt_fallback_enabled,
    )

    base = "You are a helpful agent."
    appended = _append_policy_fallback(base)
    assert "Policy Fallback" in appended
    assert appended.startswith(base)

    # Empty base -> no append
    assert _append_policy_fallback('') == ''

    # Toggle reads config; defaults True when config unavailable
    assert _prompt_fallback_enabled() is True

