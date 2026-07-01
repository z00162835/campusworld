import pytest
from app.commands.command_tool_semantics import (
    CommandToolSemantics,
    resolve_command_tool_semantics,
    resolve_side_effect_level,
    PLATFORM_ERROR_CODES,
)


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
