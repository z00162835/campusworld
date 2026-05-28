from __future__ import annotations

import pytest

from app.commands.command_tool_semantics import resolve_command_tool_semantics
from app.commands.init_commands import initialize_commands


@pytest.fixture(scope='module', autouse=True)
def _init_commands():
    initialize_commands(force_reinit=True)


@pytest.mark.unit
def test_unknown_command_semantic_pending():
    sem = resolve_command_tool_semantics('definitely_unknown_command')
    assert sem.semantic_pending is True
    assert sem.interaction_profile == 'read'


@pytest.mark.unit
def test_space_is_read_not_pending():
    sem = resolve_command_tool_semantics('space')
    assert sem.semantic_pending is False
    assert sem.interaction_profile == 'read'
    assert sem.manifest_tier == 'informational'


@pytest.mark.unit
def test_task_list_subcommand_read():
    sem = resolve_command_tool_semantics('task', args=['list'])
    assert sem.interaction_profile == 'read'


@pytest.mark.unit
def test_task_create_subcommand_mutate():
    sem = resolve_command_tool_semantics('task', args=['create'])
    assert sem.interaction_profile == 'mutate'


@pytest.mark.unit
def test_notice_list_read_publish_mutate():
    assert resolve_command_tool_semantics('notice', args=['list']).interaction_profile == 'read'
    assert resolve_command_tool_semantics('notice', args=['view', '1']).interaction_profile == 'read'
    assert resolve_command_tool_semantics('notice', args=['publish']).interaction_profile == 'mutate'


@pytest.mark.unit
def test_agent_tool_add_mutate_list_read():
    assert resolve_command_tool_semantics('agent', args=['list']).interaction_profile == 'read'
    assert resolve_command_tool_semantics('agent', args=['tool', 'add']).interaction_profile == 'mutate'
    assert resolve_command_tool_semantics('agent', args=['tool']).interaction_profile == 'read'


@pytest.mark.unit
def test_world_list_read_install_mutate():
    assert resolve_command_tool_semantics('world', args=['list']).interaction_profile == 'read'
    assert resolve_command_tool_semantics('world', args=['install', 'hicampus']).interaction_profile == 'mutate'


@pytest.mark.unit
def test_world_read_subcommand_profiles():
    assert resolve_command_tool_semantics('world', args=['status']).interaction_profile == 'read'
    assert resolve_command_tool_semantics('world', args=['validate', 'hicampus']).interaction_profile == 'read'
    assert resolve_command_tool_semantics('world', args=['bridge', 'list']).interaction_profile == 'read'
    assert resolve_command_tool_semantics('world', args=['bridge', 'validate', 'hicampus']).interaction_profile == 'read'
    assert resolve_command_tool_semantics('world', args=['content', 'validate', 'hicampus']).interaction_profile == 'read'
    assert resolve_command_tool_semantics('world', args=['content', 'diff', 'hicampus']).interaction_profile == 'read'
    assert resolve_command_tool_semantics('world', args=['content', 'apply', 'hicampus']).interaction_profile == 'mutate'
    assert resolve_command_tool_semantics('world', args=['bridge', 'add']).interaction_profile == 'mutate'
