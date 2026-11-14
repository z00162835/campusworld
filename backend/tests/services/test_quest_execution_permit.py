"""Governed Objective writes cannot bypass their in-process scoped permit."""
from contextlib import nullcontext
from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from app.services.task import task_state_machine as state
from app.services.task.errors import PreconditionFailed
from app.services.task.permissions import Principal
from app.services.task.quest_decision import QuestDecisionContext, QuestGovernanceDecision, compose_quest_decisions
from app.services.task.quest_execution_permit import (
    QuestMutationPermit, _issue_mutation_permit, enforce_quest_mutation,
)


@pytest.fixture
def scope(monkeypatch):
    context = QuestDecisionContext(quest_id=11, objective_id=21,
        actor=Principal(id=99, kind='agent'), agent_node_id=99, command_line='task start 21',
        projection_revision='7', pinned_rule_refs=('test:policy@1',), correlation_id='corr',
        quest_state_version=1, objective_state_version=2)
    from app.game_engine.agent_runtime.policy.decisions import PolicyDecision
    governance = QuestGovernanceDecision('allow', 'fixture_pass', '7', context.pinned_rule_refs, context)
    decision = compose_quest_decisions(context=context, governance=governance,
        behavior=PolicyDecision.allow('before_tool_call'))
    monkeypatch.setattr(state, 'load_node_ref', lambda *_args, **_kwargs: {
        'id': 11, 'attributes': {'governance_mode': 'enforced', 'state_version': 1}})
    return context, decision, object()


def consume(permit, context, base_session, **changes):
    args = dict(session=base_session, quest_id=11, task_id=21, event='start',
                actor=context.actor, state_version=2)
    args.update(changes)
    permit.consume(**args)


def test_permit_is_single_use(scope):
    context, decision, session = scope
    permit = _issue_mutation_permit(decision, session, 'start')
    consume(permit, context, session)
    with pytest.raises(PreconditionFailed):
        consume(permit, context, session)


@pytest.mark.parametrize('change', [{'quest_id': 12}, {'task_id': 22}, {'event': 'complete'},
    {'actor': Principal(id=1, kind='user')}, {'state_version': 3}, {'session': object()}])
def test_permit_is_not_transferable_across_scope_or_transaction(scope, change):
    context, decision, session = scope
    permit = _issue_mutation_permit(decision, session, 'start')
    with pytest.raises(PreconditionFailed):
        consume(permit, context, session, **change)


def test_constructing_a_permit_without_the_internal_issuer_does_not_authorize(scope):
    context, decision, session = scope
    with pytest.raises(PreconditionFailed):
        consume(QuestMutationPermit(decision, session, 'start'), context, session)


def test_client_like_metadata_cannot_mutate_an_enforced_quest(scope):
    context, _decision, session = scope
    with pytest.raises(PreconditionFailed):
        enforce_quest_mutation(session, attrs={'quest_id': 11}, task_id=21, event='start',
            actor=context.actor, state_version=2, permit={'allowed': True})


def test_agent_cannot_use_legacy_mode_to_skip_governance(scope, monkeypatch):
    context, _decision, session = scope
    monkeypatch.setattr(state, 'load_node_ref', lambda *_args, **_kwargs: {'attributes': {}})
    with pytest.raises(PreconditionFailed):
        enforce_quest_mutation(session, attrs={'quest_id': 11}, task_id=21, event='start',
            actor=context.actor, state_version=2, permit=None)
    enforce_quest_mutation(session, attrs={'quest_id': 11}, task_id=21, event='start',
        actor=replace(context.actor, kind='user'), state_version=2, permit=None)


def test_state_guard_consumes_fresh_permit_but_rejects_changed_quest(scope, monkeypatch):
    context, decision, session = scope
    enforce_quest_mutation(session, attrs={'quest_id': 11}, task_id=21, event='start',
        actor=context.actor, state_version=2, permit=_issue_mutation_permit(decision, session, 'start'))
    monkeypatch.setattr(state, 'load_node_ref', lambda *_args, **_kwargs: {
        'attributes': {'governance_mode': 'enforced', 'state_version': 2}})
    with pytest.raises(PreconditionFailed):
        enforce_quest_mutation(session, attrs={'quest_id': 11}, task_id=21, event='start',
            actor=context.actor, state_version=2, permit=_issue_mutation_permit(decision, session, 'start'))


def test_state_machine_rejects_direct_governed_transition_before_any_effect(scope, monkeypatch):
    context, _decision, _session = scope
    session = MagicMock()
    monkeypatch.setattr(state, '_transaction', lambda *_args: nullcontext(session))
    monkeypatch.setattr(state, '_check_idempotency', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(state, '_lock_task_node', lambda *_args, **_kwargs: {'attributes': {
        'quest_id': 11, 'current_state': 'claimed', 'state_version': 2,
        'workflow_ref': {'key': 'test', 'version': 1}}})
    monkeypatch.setattr(state, '_load_workflow_spec', lambda *_args, **_kwargs: {
        'events': {'start': {'from': ['claimed'], 'to': 'in_progress', 'required_role': 'executor'}}})
    monkeypatch.setattr(state, '_check_required_role', lambda *_args, **_kwargs: None)
    handler = MagicMock()
    monkeypatch.setitem(state._EVENT_HANDLERS, 'start', handler)
    with pytest.raises(PreconditionFailed):
        state.transition(task_id=21, event='start', actor_principal=context.actor, expected_version=2)
    handler.assert_not_called()
    session.execute.assert_not_called()
