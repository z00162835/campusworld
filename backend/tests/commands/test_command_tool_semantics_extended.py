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
