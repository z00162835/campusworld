"""Isolated governance composition; fixtures are never production policy."""
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.commands.base import CommandResult
from app.commands.game.look_command import LookCommand
from app.commands.policy_store import CommandPolicyRepository
from app.commands.registry import CommandRegistry
from app.game_engine.agent_runtime.policy.config import PolicyConfig
from app.game_engine.agent_runtime.policy.context import PolicyContext
from app.game_engine.agent_runtime.policy.decisions import PolicyDecision
from app.game_engine.agent_runtime.policy.engine import PolicyEngine
from app.services.task.quest_decision import QuestDecisionContext, QuestGovernanceDecision, compose_quest_decisions
from app.services.task.permissions import Principal
from app.services.world_interaction import command_runner
from app.services.world_interaction.types import WorldActor


@pytest.fixture
def scenario():
    return json.loads((Path(__file__).parents[1] / 'fixtures/quest_runtime/readonly_inspection_v1.json').read_text())


def decision_context(scenario, *, agent_involved=True, revision=None, pins=None):
    return QuestDecisionContext(
            quest_id=11, objective_id=21, actor=Principal(id=1, kind='user', permissions=frozenset()),
            agent_node_id=99 if agent_involved else None, command_line=scenario['command'],
            projection_revision=revision or scenario['projection_revision'],
            pinned_rule_refs=pins if pins is not None else (scenario['policy_ref'], scenario['process_ref']),
            correlation_id='test-quest-inspection',
    )


def compose(scenario, *, governance=None, behavior=None, agent_involved=True, revision=None, pins=None):
    context = decision_context(scenario, agent_involved=agent_involved, revision=revision, pins=pins)
    return compose_quest_decisions(
        governance=governance or QuestGovernanceDecision('allow', 'test_readonly_pass', scenario['projection_revision'],
            (scenario['policy_ref'], scenario['process_ref']), context),
        behavior=behavior,
        context=context,
    )


def test_readonly_scenario_still_reauthorizes_registered_command_at_execution(monkeypatch, scenario):
    assert scenario['test_only'] is True
    registry = CommandRegistry()
    command = LookCommand()
    execute = MagicMock(return_value=CommandResult.success_result('Visible room'))
    monkeypatch.setattr(command, 'execute', execute)
    assert registry.register_command(command)
    monkeypatch.setattr(command_runner, 'command_registry', registry)
    monkeypatch.setattr(command_runner, 'ensure_commands_initialized', lambda: None)
    policy = SimpleNamespace(enabled=True, policy_expr=None, required_permissions_any=[],
        required_permissions_all=[scenario['required_permission']], required_roles_any=[])
    monkeypatch.setattr(CommandPolicyRepository, 'get_policy', lambda *_args: policy)
    sem = command.tool_semantics
    behavior = PolicyEngine(config=PolicyConfig()).evaluate(PolicyContext(
        check_point='before_tool_call', command_name=command.name,
        interaction_profile=sem.interaction_profile, side_effect_level=sem.side_effect_level,
        data_classification=sem.data_classification,
    ))
    result = compose(scenario, behavior=behavior)
    assert result.may_request_command_authorization
    assert result.audit_payload()['command_authorization'] == 'required_at_execution'
    assert result.audit_payload()['quest_id'] == 11
    assert result.audit_payload()['actor'] == {'id': 1, 'kind': 'user'}
    actor = WorldActor(user_id='1', username='fixture', roles=[], permissions=[scenario['required_permission']])
    runner = command_runner.CommandRunner()
    assert runner.run(MagicMock(), actor, scenario['command']).success
    execute.assert_called_once()
    # A prior composed pass cannot override command authorization changing later.
    policy.enabled = False
    assert not runner.run(MagicMock(), actor, scenario['command']).success
    execute.assert_called_once()


def test_governance_deny_is_not_overridden_by_agent_allow(scenario):
    denied = QuestGovernanceDecision('deny', 'test_hold', scenario['projection_revision'],
        (scenario['policy_ref'], scenario['process_ref']), decision_context(scenario))
    result = compose(scenario, governance=denied, behavior=PolicyDecision.allow('before_tool_call'))
    assert result.status == 'blocked'
    assert result.reason_code == 'test_hold'


def test_agent_deny_overrides_governance_allow(scenario):
    result = compose(scenario, behavior=PolicyDecision.deny('before_tool_call', 'test_behavior_deny'))
    assert result.status == 'blocked'


def test_agent_approval_does_not_execute(scenario):
    result = compose(scenario, behavior=PolicyDecision.require_approval('before_tool_call', 'test_approval'))
    assert result.status == 'approval_required'
    assert not result.may_request_command_authorization
    assert result.audit_payload()['behavior']['decision'] == 'require_approval'


def test_actual_behavior_engine_blocks_high_write(scenario):
    behavior = PolicyEngine(config=PolicyConfig()).evaluate(PolicyContext(
        check_point='before_tool_call', command_name='test_mutation',
        interaction_profile='mutate', side_effect_level='write_high',
    ))
    assert not compose(scenario, behavior=behavior).may_request_command_authorization


@pytest.mark.parametrize('revision,pins', [('8', None), ('7', ()), ('7', ('test:readonly-inspection@2',)), ('7', ('@1',)), ('7', ('test:rule@latest',))])
def test_stale_or_unpinned_governance_blocks(scenario, revision, pins):
    assert not compose(scenario, revision=revision, pins=pins, agent_involved=False).may_request_command_authorization


def test_missing_agent_decision_blocks_but_human_path_still_needs_command_authorization(scenario):
    assert compose(scenario).reason_code == 'missing_agent_behavior_decision'
    human = compose(scenario, agent_involved=False)
    assert human.may_request_command_authorization
    assert human.audit_payload()['command_authorization'] == 'required_at_execution'


def test_quality_replan_is_not_a_tool_execution_allow(scenario):
    result = compose(scenario, behavior=PolicyDecision.replan('after_check', 'test_replan'))
    assert result.status == 'blocked'


def test_transform_cannot_silently_execute_original_command(scenario):
    behavior = replace(PolicyDecision.allow('before_tool_call'),
        decision='allow_with_transform', runtime_action='transform', transform_applied={'redact': True})
    assert compose(scenario, behavior=behavior).status == 'blocked'


@pytest.mark.parametrize('change', [
    {'quest_id': 12}, {'objective_id': 22}, {'command_line': 'task complete 21'},
    {'actor': Principal(id=2, kind='user', permissions=frozenset())},
    {'agent_node_id': 100},
])
def test_governance_result_cannot_be_reused_for_a_different_request(scenario, change):
    context = decision_context(scenario)
    governance = QuestGovernanceDecision('allow', 'fixture_pass', context.projection_revision,
        context.pinned_rule_refs, context)
    result = compose_quest_decisions(context=replace(context, **change), governance=governance,
        behavior=PolicyDecision.allow('before_tool_call'))
    assert result.status == 'blocked'
    assert result.reason_code == 'governance_context_mismatch'
