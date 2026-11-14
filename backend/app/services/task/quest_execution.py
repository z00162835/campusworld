"""Explicit transactional command execution with independent governance sources.

No capability or business rule is registered implicitly. Callers supply an
approved versioned capability registry and authoritative governance evaluator.
This executor is restricted to commands whose effects stay in the DB transaction;
external side effects require a separate durable delivery/compensation contract.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Event
from typing import Callable, Mapping, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.commands.base import CommandContext, CommandResult
from app.commands.command_tool_semantics import resolve_command_tool_semantics
from app.commands.registry import CommandRegistry
from app.commands.shell_words import split_command_line
from app.game_engine.agent_runtime.policy.context import PolicyContext
from app.game_engine.agent_runtime.policy.engine import PolicyEngine
from app.models.system.agent_memory_tables import AgentRunRecord
from app.services.task.errors import IdempotencyConflictError, OptimisticLockError, PreconditionFailed, ReferenceNotFound
from app.services.task.quest_decision import QuestDecisionContext, QuestGovernanceDecision, compose_quest_decisions, render_quest_template
from app.services.task.quest_semantic_service import can_read_semantic_node
from app.services.task.task_visibility_sql import visible_task_ids
from app.services.task.quest_interaction_service import record_projection_change


@dataclass(frozen=True)
class RegisteredQuestCapability:
    ref: str
    command_name: str
    args: tuple[str, ...] = ()
    database_transactional: bool = False
    max_duration_ms: int = 5000

    def tokens(self, context: QuestDecisionContext) -> tuple[str, ...]:
        return (self.command_name, *(render_quest_template(arg, context) for arg in self.args))


class _ExecutionStopped(Exception):
    pass


class _TransactionalSession:
    """Keep command-owned commit/rollback from escaping the execution savepoint."""
    def __init__(self, session: Session):
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    def commit(self):
        raise _ExecutionStopped('command_transaction_boundary_violation')

    def rollback(self):
        raise _ExecutionStopped('command_transaction_boundary_violation')


class QuestExecutionLedger:
    """Use existing Objective run/event tables, not synthetic graph audit nodes."""
    def lock_scope(self, session: Session, context: QuestDecisionContext) -> list[int]:
        if (not can_read_semantic_node(session, node_id=context.quest_id, actor=context.actor)
                or context.objective_id not in visible_task_ids(session, context.actor, [context.objective_id])):
            raise ReferenceNotFound('Quest Objective is not available')
        accounts = session.execute(text("""
            SELECT DISTINCT source_id FROM relationships
            WHERE type_code = 'TRACKS_QUEST' AND target_id = :quest_id AND is_active = TRUE
            ORDER BY source_id
        """), {'quest_id': context.quest_id}).all()
        account_ids = sorted({int(row.source_id) for row in accounts}
                             | ({context.actor.id} if context.actor.kind == 'user' else set()))
        # Interaction mutations use account-before-object lock order, too.
        for account_id in account_ids:
            session.execute(text("""INSERT INTO world_interaction_revisions (account_node_id, revision)
                VALUES (:account_id, 0) ON CONFLICT (account_node_id) DO NOTHING"""), {'account_id': account_id})
            session.execute(text("""SELECT revision FROM world_interaction_revisions
                WHERE account_node_id = :account_id FOR UPDATE"""), {'account_id': account_id}).first()
        session.execute(text("""SELECT id FROM nodes WHERE id = ANY(:scope_ids)
            ORDER BY id FOR UPDATE"""), {'scope_ids': [context.quest_id, context.objective_id]}).all()
        row = session.execute(text("""
            SELECT task.id, task.attributes AS objective_attributes, quest.attributes AS quest_attributes FROM nodes task
            JOIN nodes quest ON quest.id = :quest_id AND quest.type_code = 'quest' AND quest.is_active = TRUE
            JOIN relationships member ON member.target_id = task.id
              AND member.source_id = :quest_id AND member.type_code = 'HAS_OBJECTIVE'
              AND member.is_active = TRUE
            WHERE task.id = :objective_id AND task.type_code = 'task' AND task.is_active = TRUE
              AND task.attributes->>'quest_id' = :quest_ref
            FOR UPDATE OF task, member
        """), {'quest_id': context.quest_id, 'objective_id': context.objective_id,
               'quest_ref': str(context.quest_id)}).first()
        if row is None:
            raise ReferenceNotFound('Quest Objective is not available')
        return account_ids

    def validate_versions(self, session, context):
        if context.quest_state_version is None or context.objective_state_version is None:
            raise PreconditionFailed('Quest execution requires domain state versions')
        rows = session.execute(text("SELECT id, attributes FROM nodes WHERE id = ANY(:ids)"),
                               {'ids': [context.quest_id, context.objective_id]}).all()
        versions = {int(row.id): int(row.attributes.get('state_version') or 0) for row in rows}
        if (versions.get(context.quest_id) != context.quest_state_version
                or versions.get(context.objective_id) != context.objective_state_version):
            raise OptimisticLockError('Quest execution domain state changed')

    def replay(self, session: Session, context: QuestDecisionContext, key: str, fingerprint: str):
        row = session.execute(text("""
            SELECT result_summary, extra FROM task_runs
            WHERE task_node_id = :objective_id AND actor_principal_id = :actor_id
              AND actor_principal_kind = :actor_kind AND phase = 'quest_execute'
              AND extra->>'idempotency_key' = :key
            ORDER BY id DESC LIMIT 1
        """), {'objective_id': context.objective_id, 'actor_id': context.actor.id,
               'actor_kind': context.actor.kind, 'key': key}).first()
        if row is None:
            return None
        if row.extra.get('fingerprint') != fingerprint:
            raise IdempotencyConflictError('Quest action key was used for a different request')
        return dict(row.result_summary)

    def append(self, session: Session, context: QuestDecisionContext, key: str, fingerprint: str,
               capability_ref: str, outcome: dict, audit: dict, *, projection_accounts=()) -> None:
        params = {
            'objective_id': context.objective_id, 'actor_id': context.actor.id,
            'actor_kind': context.actor.kind, 'status': outcome['status'],
            'correlation_id': context.correlation_id,
            'result': json.dumps(outcome),
            'trace': json.dumps(audit),
            'extra': json.dumps({'idempotency_key': key, 'fingerprint': fingerprint,
                                'quest_id': context.quest_id, 'capability_ref': capability_ref}),
            'kind': 'quest.action.succeeded' if outcome['success'] else 'quest.action.escalated',
        }
        session.execute(text("""
            INSERT INTO task_runs (task_node_id, actor_principal_id, actor_principal_kind,
                phase, status, command_trace, result_summary, extra, correlation_id, ended_at)
            VALUES (:objective_id, :actor_id, :actor_kind, 'quest_execute', :status,
                CAST(:trace AS jsonb), CAST(:result AS jsonb), CAST(:extra AS jsonb), :correlation_id, now())
        """), params)
        session.execute(text("""
            INSERT INTO task_events (task_node_id, kind, actor_principal_id, actor_principal_kind,
                payload, correlation_id)
            VALUES (:objective_id, :kind, :actor_id, :actor_kind,
                CAST(:result AS jsonb), :correlation_id)
        """), params)
        if context.agent_node_id is not None:
            session.add(AgentRunRecord(agent_node_id=context.agent_node_id, run_id=uuid.uuid4(),
                correlation_id=context.correlation_id, phase='execute', status=outcome['status'],
                command_trace=[audit], graph_ops_summary={'quest_id': context.quest_id,
                    'objective_id': context.objective_id}, ended_at=datetime.now(timezone.utc)))
        for account_id in projection_accounts:
            record_projection_change(db_session=session, account_node_id=account_id,
                actor=context.actor, kind='quest.execution', target_node_id=context.quest_id,
                correlation_id=context.correlation_id)


class QuestActionExecutor:
    """Internal service entry; never exposed as arbitrary client command execution."""
    def __init__(self, *, capabilities: Mapping[str, RegisteredQuestCapability],
                 governance: Optional[Callable[[Session, QuestDecisionContext], QuestGovernanceDecision]] = None,
                 commands: CommandRegistry, behavior: Optional[PolicyEngine] = None,
                 ledger: Optional[QuestExecutionLedger] = None,
                 kill_switch: Callable[[], bool] = lambda: False):
        self._capabilities = dict(capabilities)
        if governance is None:
            from app.services.task.quest_governance import GraphQuestGovernance
            governance = GraphQuestGovernance()
        self._governance = governance
        self._commands = commands
        self._behavior = behavior or PolicyEngine()
        self._ledger = ledger or QuestExecutionLedger()
        self._kill_switch = kill_switch

    def execute(self, session: Session, *, context: QuestDecisionContext, capability_ref: str,
                idempotency_key: str, cancellation: Optional[Event] = None) -> dict:
        if not idempotency_key.strip() or not context.correlation_id.strip():
            raise ValueError('Quest execution requires idempotency and correlation ids')
        if (context.actor.kind not in {'user', 'agent'} or context.actor.id <= 0
                or (context.actor.kind == 'agent') != (context.agent_node_id is not None)
                or (context.agent_node_id is not None and context.actor.id != context.agent_node_id)):
            raise ValueError('Automatic execution requires the actual Agent principal')
        fingerprint = hashlib.sha256(json.dumps({
            'quest': context.quest_id, 'objective': context.objective_id,
            'capability': capability_ref, 'command': context.command_line,
            'rules': sorted(context.pinned_rule_refs), 'agent': context.agent_node_id,
        }, sort_keys=True).encode()).hexdigest()
        with session.begin_nested():
            projection_accounts = self._ledger.lock_scope(session, context) or ()
            replay = self._ledger.replay(session, context, idempotency_key, fingerprint)
            if replay is not None:
                return {**replay, 'idempotentReplay': True}
            self._ledger.validate_versions(session, context)
            audit = {'quest_id': context.quest_id, 'objective_id': context.objective_id,
                     'correlation_id': context.correlation_id,
                     'capability_ref': capability_ref, 'command_authorization': 'not_evaluated'}
            status, reason, success = 'escalated', 'execution_failed', False
            try:
                with session.begin_nested():
                    capability = self._capabilities.get(capability_ref)
                    if (capability is None or capability.ref != capability_ref
                            or capability_ref not in context.pinned_rule_refs
                            or not capability.database_transactional
                            or not 0 < capability.max_duration_ms <= 30000):
                        raise _ExecutionStopped('unregistered_or_unsupported_capability')
                    expected_tokens = capability.tokens(context)
                    tokens = tuple(split_command_line(context.command_line))
                    if tokens != expected_tokens or capability.command_name.startswith('@'):
                        raise _ExecutionStopped('capability_command_mismatch')
                    command = self._commands.get_command(tokens[0])
                    if command is None:
                        raise _ExecutionStopped('command_not_registered')
                    deadline = time.monotonic() + capability.max_duration_ms / 1000

                    def check_stop():
                        if self._kill_switch():
                            raise _ExecutionStopped('kill_switch')
                        if cancellation is not None and cancellation.is_set():
                            raise _ExecutionStopped('cancelled')
                        if time.monotonic() >= deadline:
                            raise _ExecutionStopped('deadline_exceeded')

                    check_stop()
                    sem = resolve_command_tool_semantics(tokens[0], args=tokens[1:], registry=self._commands)
                    if sem.semantic_pending:
                        raise _ExecutionStopped('command_semantics_unresolved')
                    if not command.supports_managed_transaction(list(tokens[1:])):
                        raise _ExecutionStopped('command_transaction_not_supported')
                    pg = getattr(session.get_bind().dialect, 'name', None) == 'postgresql'
                    previous_timeout = None
                    if pg:
                        previous_timeout = session.execute(text("SELECT current_setting('statement_timeout')")).scalar()
                        session.execute(text("SELECT set_config('statement_timeout', :timeout, true)"),
                                        {'timeout': str(capability.max_duration_ms)})
                    governance = self._governance(session, context)
                    if governance.capability_ref is not None and governance.capability_ref != capability_ref:
                        raise _ExecutionStopped('capability_command_mismatch')
                    behavior = self._behavior.evaluate(PolicyContext(
                        check_point='before_tool_call', command_name=tokens[0], command_args=tokens[1:],
                        interaction_profile=sem.interaction_profile, side_effect_level=sem.side_effect_level,
                        data_classification=sem.data_classification, tool_groups=sem.tool_groups,
                    )) if context.agent_node_id is not None else None
                    composed = compose_quest_decisions(context=context, governance=governance, behavior=behavior)
                    audit.update(composed.audit_payload())
                    if not composed.may_request_command_authorization:
                        raise _ExecutionStopped(composed.reason_code)
                    check_stop()
                    command_context = CommandContext(user_id=str(context.actor.id),
                        username=f'{context.actor.kind}:{context.actor.id}', session_id=f'quest:{context.quest_id}',
                        permissions=list(context.actor.permissions), roles=list(context.actor.roles),
                        managed_transaction=True,
                        db_session=_TransactionalSession(session),
                        internal_task_actor=context.actor if context.actor.kind == 'agent' else None,
                        metadata={'correlation_id': context.correlation_id})
                    authorization = self._commands.authorize_command(command, command_context)
                    audit['command_authorization'] = {'allowed': authorization.allowed, 'reason': authorization.reason}
                    if not authorization.allowed:
                        raise _ExecutionStopped('command_authorization_denied')
                    if tokens[0] == 'task' and len(tokens) >= 3 and tokens[1] in {'claim', 'start', 'complete'}:
                        if tokens[2] != str(context.objective_id):
                            raise _ExecutionStopped('capability_command_mismatch')
                        from app.services.task.quest_execution_permit import _issue_mutation_permit
                        command_context.quest_mutation_permit = _issue_mutation_permit(composed,
                            command_context.db_session, tokens[1])
                        command_context.metadata['quest_transition_idempotency_key'] = hashlib.sha256(
                            f'{context.actor.kind}:{context.actor.id}:{context.objective_id}:{idempotency_key}'.encode()).hexdigest()
                    # Failures/timeouts roll back command DB effects before retaining audit.
                    with session.begin_nested():
                        check_stop()
                        if pg:
                            session.execute(text("SELECT set_config('statement_timeout', :timeout, true)"),
                                {'timeout': str(max(1, int((deadline - time.monotonic()) * 1000)))})
                        result: CommandResult = command.execute(command_context, list(tokens[1:]))
                        check_stop()
                        if not result.success:
                            raise _ExecutionStopped('command_failed')
                    status, reason, success = 'succeeded', 'command_completed_verification_pending', True
                    if previous_timeout is not None:
                        session.execute(text("SELECT set_config('statement_timeout', :timeout, true)"),
                                        {'timeout': previous_timeout})
            except _ExecutionStopped as exc:
                reason = str(exc)
            except Exception as exc:
                # Do not persist exception text, which can contain secrets or SQL values.
                audit['error_type'] = type(exc).__name__
                reason = 'execution_error'
            outcome = {'success': success, 'status': status, 'reasonCode': reason,
                       'questId': str(context.quest_id), 'objectiveId': str(context.objective_id),
                       'actorKind': context.actor.kind, 'actorId': str(context.actor.id),
                       'correlationId': context.correlation_id, 'idempotentReplay': False}
            self._ledger.append(session, context, idempotency_key, fingerprint, capability_ref, outcome, audit,
                                projection_accounts=projection_accounts)
            return outcome
