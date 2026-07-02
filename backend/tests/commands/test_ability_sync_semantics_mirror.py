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


@pytest.mark.unit
def test_sync_tool_semantics_does_not_auto_seed_observation_policy(monkeypatch):
    """A command with no explicit observation_message_mode must not get an
    auto-derived agent_observation_policy (the old behavior seeded summary
    from the class-level mutate profile and defeated per-subcommand read
    resolution at runtime)."""
    fake_sem = CommandToolSemantics(interaction_profile='mutate')  # no observation_message_mode
    monkeypatch.setattr(
        'app.commands.ability_sync.resolve_command_tool_semantics',
        lambda name, args=None: fake_sem,
    )
    attrs = {}
    _sync_tool_semantics('task', attrs)
    assert 'agent_observation_policy' not in attrs


@pytest.mark.unit
def test_sync_tool_semantics_preserves_existing_observation_policy_when_no_explicit_mode(monkeypatch):
    """When the registry declares no explicit observation_message_mode, an
    existing agent_observation_policy (ops override or stale) is left
    untouched so ops overrides survive syncs."""
    fake_sem = CommandToolSemantics(interaction_profile='mutate')
    monkeypatch.setattr(
        'app.commands.ability_sync.resolve_command_tool_semantics',
        lambda name, args=None: fake_sem,
    )
    attrs = {'agent_observation_policy': {'message_mode': 'full'}}
    _sync_tool_semantics('task', attrs)
    assert attrs['agent_observation_policy'] == {'message_mode': 'full'}


@pytest.mark.unit
def test_sync_tool_semantics_writes_explicit_observation_policy(monkeypatch):
    """When the registry explicitly declares observation_message_mode, it is
    written (and overwrites any prior value)."""
    fake_sem = CommandToolSemantics(
        interaction_profile='read',
        observation_message_mode='full',
        observation_data_keys=('id', 'state'),
    )
    monkeypatch.setattr(
        'app.commands.ability_sync.resolve_command_tool_semantics',
        lambda name, args=None: fake_sem,
    )
    attrs = {'agent_observation_policy': {'message_mode': 'summary'}}
    _sync_tool_semantics('look', attrs)
    assert attrs['agent_observation_policy'] == {'message_mode': 'full', 'data_keys': ['id', 'state']}
