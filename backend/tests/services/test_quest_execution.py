"""Registered transactional execution contracts without live database writes."""
import json
from contextlib import contextmanager
from dataclasses import replace
from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.commands.base import CommandResult
from app.commands.game.look_command import LookCommand
from app.commands.game.task._helpers import principal_from_context
from app.commands.policy_store import CommandPolicyRepository
from app.commands.registry import CommandRegistry
from app.game_engine.agent_runtime.policy.config import PolicyConfig
from app.game_engine.agent_runtime.policy.config import GateDomainConfig
from app.game_engine.agent_runtime.policy.engine import PolicyEngine
from app.services.task.errors import IdempotencyConflictError
from app.services.task.permissions import Principal
from app.services.task.quest_decision import QuestDecisionContext, QuestGovernanceDecision
from app.services.task.quest_execution import QuestActionExecutor, QuestExecutionLedger, RegisteredQuestCapability


class TransactionSession:
    def __init__(self):
        self.effects = []

    @contextmanager
    def begin_nested(self):
        count = len(self.effects)
        try:
            yield
        except Exception:
            del self.effects[count:]
            raise

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name='sqlite'))


class MemoryLedger:
    def __init__(self):
        self.entries = {}
        self.audits = []

    def lock_scope(self, session, context):
        pass

    def validate_versions(self, session, context):
        pass

    def replay(self, session, context, key, fingerprint):
        prior = self.entries.get(key)
        if prior is None:
            return None
        if prior[0] != fingerprint:
            raise IdempotencyConflictError('key reused')
        return prior[1]

    def append(self, session, context, key, fingerprint, capability_ref, outcome, audit, **_kwargs):
        self.entries[key] = (fingerprint, outcome)
        self.audits.append(audit)


@pytest.fixture
def runtime(monkeypatch):
    from app.services.task import task_state_machine

    monkeypatch.setattr(task_state_machine, 'load_node_ref', lambda *_args, **_kwargs: {'id': 99})
    context = QuestDecisionContext(quest_id=11, objective_id=21,
        actor=Principal(id=99, kind='agent', permissions=frozenset({'task.read'})),
        agent_node_id=99, command_line='look', projection_revision='7',
        quest_state_version=1, objective_state_version=2,
        pinned_rule_refs=('test:readonly-policy@1', 'test:inspect-context@1'), correlation_id='corr-run')
    registry = CommandRegistry()
    command = LookCommand()
    calls = []

    def execute(ctx, args):
        calls.append(principal_from_context(ctx))
        ctx.db_session.effects.append('transactional_command_effect')
        return CommandResult.success_result('observed')

    monkeypatch.setattr(command, 'execute', execute)
    registry.register_command(command)
    policy = SimpleNamespace(enabled=True, policy_expr=None, required_permissions_any=[],
        required_permissions_all=['task.read'], required_roles_any=[])
    monkeypatch.setattr(CommandPolicyRepository, 'get_policy', lambda *_args: policy)
    governance = MagicMock(side_effect=lambda _session, ctx: QuestGovernanceDecision(
        'allow', 'fixture_pass', ctx.projection_revision, ctx.pinned_rule_refs, ctx))
    ledger = MemoryLedger()
    capability = RegisteredQuestCapability(ref='test:inspect-context@1', command_name='look', database_transactional=True)
    executor = QuestActionExecutor(capabilities={capability.ref: capability}, governance=governance,
        commands=registry, behavior=PolicyEngine(config=PolicyConfig()), ledger=ledger)
    return SimpleNamespace(executor=executor, ledger=ledger, context=context, session=TransactionSession(),
        governance=governance, calls=calls, command=command, policy=policy, capability=capability)


def run(runtime, **kwargs):
    return runtime.executor.execute(runtime.session, context=kwargs.pop('context', runtime.context),
        capability_ref=kwargs.pop('capability_ref', runtime.capability.ref),
        idempotency_key=kwargs.pop('idempotency_key', 'execute-1'), **kwargs)


def test_explicit_execution_preserves_agent_identity_and_does_not_accept_quest(runtime):
    result = run(runtime)
    assert result['success'] is True
    assert result['reasonCode'] == 'command_completed_verification_pending'
    assert runtime.calls == [runtime.context.actor]
    assert runtime.ledger.audits[0]['command_authorization']['allowed'] is True
    assert runtime.ledger.audits[0]['behavior']['check_point'] == 'before_tool_call'
    assert runtime.session.effects == ['transactional_command_effect']


def test_idempotent_replay_does_not_repeat_command_or_evaluations(runtime):
    run(runtime)
    replay = run(runtime)
    assert replay['idempotentReplay'] is True
    assert len(runtime.calls) == 1
    runtime.governance.assert_called_once()


def test_key_reuse_for_changed_request_is_rejected(runtime):
    run(runtime)
    with pytest.raises(IdempotencyConflictError):
        run(runtime, context=replace(runtime.context, command_line='task complete 21'))
    assert len(runtime.calls) == 1


def test_no_capability_or_arbitrary_command_is_executed(runtime):
    result = run(runtime, capability_ref='unknown:action@1')
    assert result['reasonCode'] == 'unregistered_or_unsupported_capability'
    runtime.governance.assert_not_called()
    assert runtime.calls == []


def test_command_injection_cannot_replace_registered_tokens(runtime):
    result = run(runtime, context=replace(runtime.context, command_line='task complete 21'))
    assert result['reasonCode'] == 'capability_command_mismatch'
    assert runtime.calls == []


def test_governance_denial_persists_escalation_without_command(runtime):
    runtime.governance.side_effect = lambda _session, ctx: QuestGovernanceDecision(
        'deny', 'missing_evidence', ctx.projection_revision, ctx.pinned_rule_refs, ctx)
    result = run(runtime)
    assert result['status'] == 'escalated'
    assert result['reasonCode'] == 'missing_evidence'
    assert runtime.calls == []
    assert runtime.ledger.audits[0]['governance']['decision'] == 'deny'


def test_final_authorization_is_not_overridden_by_governance_allow(runtime):
    runtime.policy.enabled = False
    assert run(runtime)['reasonCode'] == 'command_authorization_denied'
    assert runtime.calls == []


def test_cancelled_execution_is_audited_without_invocation(runtime):
    cancelled = Event()
    cancelled.set()
    assert run(runtime, cancellation=cancelled)['reasonCode'] == 'cancelled'
    assert runtime.calls == []


def test_kill_switch_after_command_rolls_back_effects(runtime):
    runtime.executor._kill_switch = lambda: bool(runtime.calls)
    assert run(runtime)['reasonCode'] == 'kill_switch'
    assert len(runtime.calls) == 1
    assert runtime.session.effects == []


def test_deadline_after_command_rolls_back_effects(runtime, monkeypatch):
    from app.services.task import quest_execution

    clock = [100.0]
    monkeypatch.setattr(quest_execution.time, 'monotonic', lambda: clock[0])
    original = runtime.command.execute

    def slow(ctx, args):
        result = original(ctx, args)
        clock[0] += 10
        return result

    runtime.command.execute = slow
    assert run(runtime)['reasonCode'] == 'deadline_exceeded'
    assert runtime.session.effects == []


def test_command_cannot_commit_outside_runtime_transaction(runtime):
    runtime.command.execute = lambda ctx, args: ctx.db_session.commit()
    assert run(runtime)['reasonCode'] == 'command_transaction_boundary_violation'


def test_provider_failure_rolls_back_and_does_not_persist_sensitive_exception(runtime):
    def fail(session, _ctx):
        session.effects.append('must_rollback')
        raise ValueError('secret-token')
    runtime.governance.side_effect = fail
    assert run(runtime)['reasonCode'] == 'execution_error'
    assert runtime.session.effects == []
    assert 'secret-token' not in str(runtime.ledger.audits)


def test_agent_cannot_masquerade_as_user_or_skip_agent_behavior(runtime):
    with pytest.raises(ValueError):
        run(runtime, context=replace(runtime.context, actor=replace(runtime.context.actor, kind='user')))
    with pytest.raises(ValueError):
        run(runtime, context=replace(runtime.context, agent_node_id=None))
    assert runtime.calls == []


def test_sql_ledger_records_decisions_outcomes_and_actual_agent_run(runtime):
    session = MagicMock()
    result = {'success': False, 'status': 'escalated', 'reasonCode': 'missing_evidence'}
    QuestExecutionLedger().append(session, runtime.context, 'key', 'hash', runtime.capability.ref,
        result, {'governance': {'decision': 'deny'}, 'command_authorization': 'not_evaluated'})
    assert session.execute.call_count == 2
    params = session.execute.call_args.args[1]
    assert params['actor_kind'] == 'agent'
    assert params['kind'] == 'quest.action.escalated'
    assert json.loads(params['result']) == result
    assert json.loads(params['extra'])['quest_id'] == 11
    record = session.add.call_args.args[0]
    assert record.agent_node_id == 99
    assert record.status == 'escalated'
    session.commit.assert_not_called()


def test_actual_task_start_keeps_agent_and_command_in_the_runtime_session(runtime, monkeypatch):
    from app.commands.game.task import task_command as task_module
    from app.services.task.task_state_machine import TransitionResult

    command = task_module.TaskCommand()
    runtime.executor._commands.register_command(command)
    runtime.executor._capabilities[runtime.capability.ref] = replace(runtime.capability,
        command_name='task', args=('start', '{objective_id}'))
    runtime.context = replace(runtime.context, command_line='task start 21', actor=replace(
        runtime.context.actor, permissions=frozenset({'task.read', 'task.update'})))
    runtime.executor._behavior = PolicyEngine(config=PolicyConfig(gate=GateDomainConfig(
        side_effect_defaults={'none': 'allow', 'read': 'allow', 'write_low': 'allow', 'write_high': 'allow'})))
    runtime.session.execute = lambda *_args, **_kwargs: SimpleNamespace(first=lambda: (2,))
    transition_calls = []

    def transition(**kwargs):
        transition_calls.append(kwargs)
        kwargs['db_session'].effects.append('task_started')
        return TransitionResult(task_id=21, from_state='claimed', to_state='in_progress', event='start',
            event_seq=3, state_version=3, idempotent_replay=False, correlation_id='corr-run', trace_id='trace-run')

    monkeypatch.setattr(task_module, 'transition', transition)
    assert run(runtime)['success'] is True
    assert len(transition_calls) == 1
    assert transition_calls[0]['actor_principal'].kind == 'agent'
    assert transition_calls[0]['db_session']._session is runtime.session
    assert runtime.session.effects == ['task_started']


def test_write_branch_without_transaction_support_is_not_invoked(runtime):
    from app.commands.game.task.task_command import TaskCommand
    runtime.executor._commands.register_command(TaskCommand())
    runtime.executor._capabilities[runtime.capability.ref] = replace(runtime.capability,
        command_name='task', args=('create', '--title', 'not allowed'))
    runtime.context = replace(runtime.context, command_line='task create --title "not allowed"')
    assert run(runtime)['reasonCode'] == 'command_transaction_not_supported'


def test_sql_ledger_validates_both_domain_versions(runtime):
    from app.services.task.errors import OptimisticLockError, PreconditionFailed

    session = MagicMock()
    session.execute.return_value.all.return_value = [SimpleNamespace(id=11, attributes={'state_version': 1}),
        SimpleNamespace(id=21, attributes={'state_version': 2})]
    ledger = QuestExecutionLedger()
    ledger.validate_versions(session, runtime.context)
    with pytest.raises(OptimisticLockError):
        ledger.validate_versions(session, replace(runtime.context, objective_state_version=1))
    with pytest.raises(PreconditionFailed):
        ledger.validate_versions(session, replace(runtime.context, quest_state_version=None))


def test_sql_ledger_notifies_each_locked_tracking_account(runtime, monkeypatch):
    from app.services.task import quest_execution as module

    notify = MagicMock()
    monkeypatch.setattr(module, 'record_projection_change', notify)
    session = MagicMock()
    QuestExecutionLedger().append(session, runtime.context, 'key', 'hash', runtime.capability.ref,
        {'success': True, 'status': 'succeeded'}, {}, projection_accounts=(1, 2))
    assert [call.kwargs['account_node_id'] for call in notify.call_args_list] == [1, 2]
    assert all(call.kwargs['actor'] == runtime.context.actor for call in notify.call_args_list)
    session.commit.assert_not_called()
