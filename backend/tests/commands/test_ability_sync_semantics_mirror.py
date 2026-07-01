"""Unit tests for ability_sync mirroring of extended tool contract fields."""
import pytest

from app.commands.command_tool_semantics import CommandToolSemantics
from app.commands.ability_sync import _sync_tool_semantics


@pytest.mark.unit
def test_sync_tool_semantics_mirrors_new_fields(monkeypatch):
    fake_sem = CommandToolSemantics(
        interaction_profile='mutate',
        side_effect_level='write_high',
        idempotent=False,
        deterministic=False,
        input_schema={'type': 'object', 'properties': {'name': {'type': 'string'}}},
        output_schema={'type': 'object'},
        error_schema={'type': 'object'},
        data_classification='confidential',
        data_scope=('task',),
    )
    monkeypatch.setattr(
        'app.commands.ability_sync.resolve_command_tool_semantics',
        lambda name, args=None: fake_sem,
    )
    attrs = {}
    _sync_tool_semantics('task', attrs)
    assert attrs['side_effect_level'] == 'write_high'
    assert attrs['idempotent'] is False
    assert attrs['deterministic'] is False
    assert attrs['input_schema'] == {'type': 'object', 'properties': {'name': {'type': 'string'}}}
    assert attrs['output_schema'] == {'type': 'object'}
    assert attrs['error_schema'] == {'type': 'object'}
    assert attrs['data_classification'] == 'confidential'
    assert attrs['data_scope'] == ['task']


@pytest.mark.unit
def test_sync_tool_semantics_derives_side_effect_level_when_unset(monkeypatch):
    fake_sem = CommandToolSemantics(interaction_profile='read')  # side_effect_level None
    monkeypatch.setattr(
        'app.commands.ability_sync.resolve_command_tool_semantics',
        lambda name, args=None: fake_sem,
    )
    attrs = {}
    _sync_tool_semantics('look', attrs)
    assert attrs['side_effect_level'] == 'read'  # derived
    # None schemas are popped (omit-None behavior), so the key is absent.
    assert 'input_schema' not in attrs


@pytest.mark.unit
def test_sync_tool_semantics_omits_none_schemas(monkeypatch):
    fake_sem = CommandToolSemantics(interaction_profile='read')
    monkeypatch.setattr(
        'app.commands.ability_sync.resolve_command_tool_semantics',
        lambda name, args=None: fake_sem,
    )
    attrs = {}
    _sync_tool_semantics('help', attrs)
    # None schemas must not create keys (keep node attrs clean)
    assert 'input_schema' not in attrs
    assert 'output_schema' not in attrs
    assert 'error_schema' not in attrs
    assert 'data_classification' not in attrs
    assert 'data_scope' not in attrs
