"""Authoritative mutations for account-scoped Quest interaction state."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.task.errors import (
    IdempotencyConflictError,
    OptimisticLockError,
    PermissionDenied,
    PreconditionFailed,
    ReferenceNotFound,
)
from app.services.task.permissions import Principal, TASK_ADMIN, TASK_READ, TASK_UPDATE
from app.services.task.quest_semantic_service import can_read_semantic_node
from app.services.task.task_state_machine import insert_relationship, load_node_ref, task_transaction
from app.services.task.task_visibility_sql import visible_task_ids


@dataclass(frozen=True)
class QuestInteractionMutationResult:
    projection_revision: str
    last_event_id: Optional[str]
    idempotent_replay: bool
    changed: bool
    relationship_id: Optional[int] = None


def read_projection_cursor(session: Session, *, account_node_id: int) -> tuple[str, Optional[str]]:
    row = session.execute(
        text(
            """
            SELECT revision, last_event_id
              FROM world_interaction_revisions
             WHERE account_node_id = :account_id
            """
        ),
        {'account_id': int(account_node_id)},
    ).first()
    if row is None:
        return '0', None
    return str(int(row.revision)), str(int(row.last_event_id)) if row.last_event_id is not None else None


def _authorize_account(actor: Principal, account_node_id: int, permission: str) -> None:
    if actor.kind != 'system' and int(actor.id) != int(account_node_id) and not actor.has_permission(TASK_ADMIN):
        raise PermissionDenied('actor cannot modify another account interaction state')
    if actor.kind != 'system' and not actor.has_permission(permission) and not actor.has_permission(TASK_ADMIN):
        raise PermissionDenied(f'{permission} is required')


def _replay(
    session: Session,
    *,
    account_node_id: int,
    idempotency_key: str,
    request_fingerprint: str,
) -> Optional[QuestInteractionMutationResult]:
    row = session.execute(
        text(
            """
            SELECT id, revision, payload
              FROM world_interaction_events
             WHERE account_node_id = :account_id
               AND idempotency_key = :idempotency_key
            """
        ),
        {'account_id': int(account_node_id), 'idempotency_key': idempotency_key},
    ).first()
    if row is None:
        return None
    payload = row.payload if isinstance(row.payload, dict) else json.loads(row.payload or '{}')
    if payload.get('_request_fingerprint') != request_fingerprint:
        raise IdempotencyConflictError('idempotencyKey was already used for a different Quest interaction request')
    return QuestInteractionMutationResult(
        projection_revision=str(int(row.revision)),
        last_event_id=str(int(row.id)),
        idempotent_replay=True,
        changed=bool(payload.get('changed', True)),
        relationship_id=int(payload['relationship_id']) if payload.get('relationship_id') is not None else None,
    )


def _lock_cursor(session: Session, *, account_node_id: int, expected_revision: str) -> int:
    session.execute(
        text(
            """
            INSERT INTO world_interaction_revisions (account_node_id, revision, updated_at)
            VALUES (:account_id, 0, now())
            ON CONFLICT (account_node_id) DO NOTHING
            """
        ),
        {'account_id': int(account_node_id)},
    )
    row = session.execute(
        text(
            """
            SELECT revision
              FROM world_interaction_revisions
             WHERE account_node_id = :account_id
             FOR UPDATE
            """
        ),
        {'account_id': int(account_node_id)},
    ).first()
    current = int(row.revision if row is not None else 0)
    try:
        expected = int(str(expected_revision))
    except (TypeError, ValueError) as exc:
        raise PreconditionFailed('expectedProjectionRevision must be an opaque revision returned by the server') from exc
    if current != expected:
        raise OptimisticLockError(f'stale_projection: expected={expected} current={current}')
    return current


def _append_event(
    session: Session,
    *,
    account_node_id: int,
    current_revision: int,
    kind: str,
    target_node_id: Optional[int],
    actor: Principal,
    idempotency_key: str,
    correlation_id: Optional[str],
    payload: Dict[str, Any],
    request_fingerprint: str,
) -> QuestInteractionMutationResult:
    next_revision = current_revision + 1
    row = session.execute(
        text(
            """
            INSERT INTO world_interaction_events
                (account_node_id, revision, kind, target_node_id,
                 actor_principal_id, actor_principal_kind, correlation_id,
                 idempotency_key, payload, created_at)
            VALUES
                (:account_id, :revision, :kind, :target_id,
                 :actor_id, :actor_kind, :correlation_id,
                 :idempotency_key, CAST(:payload AS jsonb), now())
            RETURNING id
            """
        ),
        {
            'account_id': int(account_node_id),
            'revision': next_revision,
            'kind': kind,
            'target_id': int(target_node_id) if target_node_id is not None else None,
            'actor_id': int(actor.id) if actor.kind != 'system' else None,
            'actor_kind': actor.kind,
            'correlation_id': correlation_id,
            'idempotency_key': idempotency_key,
            'payload': json.dumps({**payload, '_request_fingerprint': request_fingerprint}, ensure_ascii=False),
        },
    ).first()
    event_id = int(row.id)
    session.execute(
        text(
            """
            UPDATE world_interaction_revisions
               SET revision = :revision,
                   last_event_id = :event_id,
                   updated_at = now()
             WHERE account_node_id = :account_id
            """
        ),
        {'revision': next_revision, 'event_id': event_id, 'account_id': int(account_node_id)},
    )
    return QuestInteractionMutationResult(
        projection_revision=str(next_revision),
        last_event_id=str(event_id),
        idempotent_replay=False,
        changed=bool(payload.get('changed', True)),
        relationship_id=payload.get('relationship_id'),
    )


def _mutation_context(
    session: Session,
    *,
    account_node_id: int,
    actor: Principal,
    expected_revision: str,
    idempotency_key: str,
    permission: str = TASK_READ,
    kind: str,
    request_payload: Dict[str, Any],
) -> tuple[Optional[QuestInteractionMutationResult], int, str]:
    if not str(idempotency_key or '').strip():
        raise PreconditionFailed('idempotencyKey is required')
    _authorize_account(actor, account_node_id, permission)
    load_node_ref(session, node_id=int(account_node_id), expected_type_code='account')
    request_fingerprint = hashlib.sha256(
        json.dumps({'kind': kind, 'payload': request_payload}, sort_keys=True, separators=(',', ':')).encode('utf-8')
    ).hexdigest()
    replay = _replay(
        session,
        account_node_id=account_node_id,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
    )
    if replay is not None:
        return replay, int(replay.projection_revision), request_fingerprint
    return None, _lock_cursor(session, account_node_id=account_node_id, expected_revision=expected_revision), request_fingerprint


def _unchanged_result(
    session: Session,
    *,
    account_node_id: int,
    current_revision: int,
    relationship_id: Optional[int] = None,
) -> QuestInteractionMutationResult:
    _, last_event_id = read_projection_cursor(session, account_node_id=account_node_id)
    return QuestInteractionMutationResult(
        projection_revision=str(current_revision),
        last_event_id=last_event_id,
        idempotent_replay=False,
        changed=False,
        relationship_id=relationship_id,
    )


def record_projection_change(
    *,
    db_session: Session,
    account_node_id: int,
    actor: Principal,
    kind: str,
    target_node_id: Optional[int] = None,
    correlation_id: Optional[str] = None,
) -> QuestInteractionMutationResult:
    """Advance the account cursor for a successful non-Quest mutation."""
    with task_transaction(db_session) as session:
        session.execute(
            text(
                """
                INSERT INTO world_interaction_revisions (account_node_id, revision, updated_at)
                VALUES (:account_id, 0, now())
                ON CONFLICT (account_node_id) DO NOTHING
                """
            ),
            {'account_id': int(account_node_id)},
        )
        row = session.execute(
            text(
                """
                SELECT revision
                  FROM world_interaction_revisions
                 WHERE account_node_id = :account_id
                 FOR UPDATE
                """
            ),
            {'account_id': int(account_node_id)},
        ).first()
        current_revision = int(row.revision if row is not None else 0)
        request_id = str(uuid.uuid4())
        fingerprint = hashlib.sha256(f'{kind}:{target_node_id or ""}:{request_id}'.encode('utf-8')).hexdigest()
        return _append_event(
            session,
            account_node_id=account_node_id,
            current_revision=current_revision,
            kind=kind,
            target_node_id=target_node_id,
            actor=actor,
            idempotency_key=f'projection-{request_id}',
            correlation_id=correlation_id,
            payload={'changed': True},
            request_fingerprint=fingerprint,
        )


def _readable_quest(session: Session, *, quest_id: int, actor: Principal) -> Dict[str, Any]:
    quest = load_node_ref(session, node_id=int(quest_id), expected_type_code='quest')
    if not can_read_semantic_node(session, node_id=int(quest_id), actor=actor):
        raise ReferenceNotFound(f'quest {quest_id} not found')
    return quest


def _active_relationship(
    session: Session,
    *,
    source_id: int,
    target_id: int,
    type_code: str,
) -> Optional[int]:
    row = session.execute(
        text(
            """
            SELECT id
              FROM relationships
             WHERE source_id = :source_id
               AND target_id = :target_id
               AND type_code = :type_code
               AND is_active = TRUE
             LIMIT 1
            """
        ),
        {'source_id': int(source_id), 'target_id': int(target_id), 'type_code': type_code},
    ).first()
    return int(row.id) if row is not None else None


def _active_clue_pin(
    session: Session,
    *,
    account_node_id: int,
    clue_node_id: int,
    quest_id: int,
) -> Optional[int]:
    """Resolve a pin by its full account + Quest + clue identity."""
    row = session.execute(
        text(
            """
            SELECT id
              FROM relationships
             WHERE source_id = :account_id
               AND target_id = :clue_id
               AND type_code = 'PINS_CLUE'
               AND is_active = TRUE
               AND attributes->>'quest_id' = :quest_id
             LIMIT 1
            """
        ),
        {
            'account_id': int(account_node_id),
            'clue_id': int(clue_node_id),
            'quest_id': str(int(quest_id)),
        },
    ).first()
    return int(row.id) if row is not None else None


def _relationship_attributes(session: Session, relationship_id: int) -> Dict[str, Any]:
    row = session.execute(
        text("SELECT attributes FROM relationships WHERE id = :relationship_id"),
        {'relationship_id': int(relationship_id)},
    ).first()
    if row is None:
        return {}
    return row.attributes if isinstance(row.attributes, dict) else json.loads(row.attributes or '{}')


def _edge_metadata(actor: Principal, correlation_id: Optional[str], **extra: Any) -> Dict[str, Any]:
    return {
        'actor_principal_id': int(actor.id) if actor.kind != 'system' else None,
        'actor_principal_kind': actor.kind,
        'correlation_id': correlation_id,
        **extra,
    }


def track_quest(
    *,
    account_node_id: int,
    quest_id: int,
    actor: Principal,
    expected_revision: str,
    idempotency_key: str,
    correlation_id: Optional[str] = None,
    db_session: Optional[Session] = None,
) -> QuestInteractionMutationResult:
    with task_transaction(db_session) as session:
        replay, revision, fingerprint = _mutation_context(
            session,
            account_node_id=account_node_id,
            actor=actor,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
            kind='quest.tracked',
            request_payload={'quest_id': quest_id},
        )
        if replay is not None:
            return replay
        _readable_quest(session, quest_id=quest_id, actor=actor)
        relationship_id = _active_relationship(
            session, source_id=account_node_id, target_id=quest_id, type_code='TRACKS_QUEST'
        )
        changed = relationship_id is None
        if not changed:
            return _unchanged_result(
                session,
                account_node_id=account_node_id,
                current_revision=revision,
                relationship_id=relationship_id,
            )
        if relationship_id is None:
            relationship_id = insert_relationship(
                session,
                source_id=account_node_id,
                target_id=quest_id,
                type_code='TRACKS_QUEST',
                attributes=_edge_metadata(actor, correlation_id),
                tags=['quest_interaction'],
            )
        return _append_event(
            session,
            account_node_id=account_node_id,
            current_revision=revision,
            kind='quest.tracked',
            target_node_id=quest_id,
            actor=actor,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            payload={'changed': changed, 'quest_id': quest_id, 'relationship_id': relationship_id},
            request_fingerprint=fingerprint,
        )


def untrack_quest(
    *,
    account_node_id: int,
    quest_id: int,
    actor: Principal,
    expected_revision: str,
    idempotency_key: str,
    correlation_id: Optional[str] = None,
    db_session: Optional[Session] = None,
) -> QuestInteractionMutationResult:
    with task_transaction(db_session) as session:
        replay, revision, fingerprint = _mutation_context(
            session,
            account_node_id=account_node_id,
            actor=actor,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
            kind='quest.untracked',
            request_payload={'quest_id': quest_id},
        )
        if replay is not None:
            return replay
        _readable_quest(session, quest_id=quest_id, actor=actor)
        rows = session.execute(
            text(
                """
                UPDATE relationships
                   SET is_active = FALSE,
                       attributes = COALESCE(attributes, '{}'::jsonb)
                           || CAST(:metadata AS jsonb),
                       updated_at = now()
                 WHERE source_id = :account_id
                   AND target_id = :quest_id
                   AND type_code = 'TRACKS_QUEST'
                   AND is_active = TRUE
                RETURNING id
                """
            ),
            {
                'account_id': int(account_node_id),
                'quest_id': int(quest_id),
                'metadata': json.dumps(_edge_metadata(actor, correlation_id, removed=True), ensure_ascii=False),
            },
        ).all()
        if not rows:
            return _unchanged_result(session, account_node_id=account_node_id, current_revision=revision)
        session.execute(
            text(
                """
                UPDATE relationships focus
                   SET is_active = FALSE,
                       attributes = COALESCE(focus.attributes, '{}'::jsonb)
                           || CAST(:metadata AS jsonb),
                       updated_at = now()
                 WHERE focus.source_id = :account_id
                   AND focus.type_code = 'FOCUSES_ON'
                   AND focus.is_active = TRUE
                   AND EXISTS (
                       SELECT 1
                         FROM relationships member
                        WHERE member.source_id = :quest_id
                          AND member.target_id = focus.target_id
                          AND member.type_code = 'HAS_OBJECTIVE'
                          AND member.is_active = TRUE
                   )
                """
            ),
            {
                'account_id': int(account_node_id),
                'quest_id': int(quest_id),
                'metadata': json.dumps(_edge_metadata(actor, correlation_id, cleared_by_untrack=True), ensure_ascii=False),
            },
        )
        return _append_event(
            session,
            account_node_id=account_node_id,
            current_revision=revision,
            kind='quest.untracked',
            target_node_id=quest_id,
            actor=actor,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            payload={'changed': bool(rows), 'quest_id': quest_id},
            request_fingerprint=fingerprint,
        )


def focus_objective(
    *,
    account_node_id: int,
    quest_id: int,
    objective_id: int,
    actor: Principal,
    expected_revision: str,
    idempotency_key: str,
    correlation_id: Optional[str] = None,
    db_session: Optional[Session] = None,
) -> QuestInteractionMutationResult:
    with task_transaction(db_session) as session:
        replay, revision, fingerprint = _mutation_context(
            session,
            account_node_id=account_node_id,
            actor=actor,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
            kind='quest.objective_focused',
            request_payload={'quest_id': quest_id, 'objective_id': objective_id},
        )
        if replay is not None:
            return replay
        _readable_quest(session, quest_id=quest_id, actor=actor)
        load_node_ref(session, node_id=int(objective_id), expected_type_code='task')
        if int(objective_id) not in visible_task_ids(session, actor, [int(objective_id)]):
            raise ReferenceNotFound(f'objective {objective_id} not found')
        if _active_relationship(
            session, source_id=account_node_id, target_id=quest_id, type_code='TRACKS_QUEST'
        ) is None:
            raise PreconditionFailed('quest must be tracked before focusing an objective')
        if _active_relationship(
            session, source_id=quest_id, target_id=objective_id, type_code='HAS_OBJECTIVE'
        ) is None:
            raise ReferenceNotFound('objective does not belong to the quest')
        existing = _active_relationship(
            session, source_id=account_node_id, target_id=objective_id, type_code='FOCUSES_ON'
        )
        changed = existing is None
        if not changed:
            return _unchanged_result(
                session,
                account_node_id=account_node_id,
                current_revision=revision,
                relationship_id=existing,
            )
        if changed:
            session.execute(
                text(
                    """
                    UPDATE relationships
                       SET is_active = FALSE,
                           attributes = COALESCE(attributes, '{}'::jsonb)
                               || CAST(:metadata AS jsonb),
                           updated_at = now()
                     WHERE source_id = :account_id
                       AND type_code = 'FOCUSES_ON'
                       AND is_active = TRUE
                    """
                ),
                {
                    'account_id': int(account_node_id),
                    'metadata': json.dumps(_edge_metadata(actor, correlation_id, replaced=True), ensure_ascii=False),
                },
            )
            existing = insert_relationship(
                session,
                source_id=account_node_id,
                target_id=objective_id,
                type_code='FOCUSES_ON',
                attributes=_edge_metadata(actor, correlation_id, quest_id=int(quest_id)),
                tags=['quest_interaction'],
            )
        return _append_event(
            session,
            account_node_id=account_node_id,
            current_revision=revision,
            kind='quest.objective_focused',
            target_node_id=objective_id,
            actor=actor,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            payload={
                'changed': changed,
                'quest_id': quest_id,
                'objective_id': objective_id,
                'relationship_id': existing,
            },
            request_fingerprint=fingerprint,
        )


def set_clue_pin(
    *,
    account_node_id: int,
    quest_id: int,
    clue_node_id: int,
    pinned: bool,
    actor: Principal,
    expected_revision: str,
    idempotency_key: str,
    correlation_id: Optional[str] = None,
    db_session: Optional[Session] = None,
) -> QuestInteractionMutationResult:
    with task_transaction(db_session) as session:
        event_kind = 'quest.clue_pinned' if pinned else 'quest.clue_unpinned'
        replay, revision, fingerprint = _mutation_context(
            session,
            account_node_id=account_node_id,
            actor=actor,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
            kind=event_kind,
            request_payload={'quest_id': quest_id, 'clue_node_id': clue_node_id},
        )
        if replay is not None:
            return replay
        _readable_quest(session, quest_id=quest_id, actor=actor)
        if _active_relationship(
            session, source_id=account_node_id, target_id=quest_id, type_code='TRACKS_QUEST'
        ) is None:
            raise PreconditionFailed('quest must be tracked before pinning clues')
        clue = load_node_ref(session, node_id=int(clue_node_id))
        if clue['type_code'] not in {'observation', 'fact', 'evidence'}:
            raise PreconditionFailed('clue must be a materialized observation, fact, or evidence node')
        if not can_read_semantic_node(session, node_id=int(clue_node_id), actor=actor):
            raise ReferenceNotFound(f'clue {clue_node_id} not found')
        existing = _active_clue_pin(
            session,
            account_node_id=account_node_id,
            clue_node_id=clue_node_id,
            quest_id=quest_id,
        )
        changed = (pinned and existing is None) or (not pinned and existing is not None)
        if not changed:
            return _unchanged_result(
                session,
                account_node_id=account_node_id,
                current_revision=revision,
                relationship_id=existing,
            )
        if pinned and existing is None:
            existing = insert_relationship(
                session,
                source_id=account_node_id,
                target_id=clue_node_id,
                type_code='PINS_CLUE',
                attributes=_edge_metadata(actor, correlation_id, quest_id=int(quest_id)),
                tags=['quest_interaction'],
            )
        elif not pinned and existing is not None:
            session.execute(
                text(
                    """
                    UPDATE relationships
                       SET is_active = FALSE,
                           attributes = COALESCE(attributes, '{}'::jsonb)
                               || CAST(:metadata AS jsonb),
                           updated_at = now()
                     WHERE id = :relationship_id
                    """
                ),
                {
                    'relationship_id': existing,
                    'metadata': json.dumps(_edge_metadata(actor, correlation_id, removed=True), ensure_ascii=False),
                },
            )
        return _append_event(
            session,
            account_node_id=account_node_id,
            current_revision=revision,
            kind=event_kind,
            target_node_id=clue_node_id,
            actor=actor,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            payload={
                'changed': changed,
                'quest_id': quest_id,
                'clue_node_id': clue_node_id,
                'relationship_id': existing,
            },
            request_fingerprint=fingerprint,
        )


def set_collaborator(
    *,
    account_node_id: int,
    quest_id: int,
    agent_node_id: int,
    active: bool,
    actor: Principal,
    expected_revision: str,
    idempotency_key: str,
    role: str = 'advisor',
    status: str = 'active',
    is_primary_companion: bool = False,
    capability_scope: Optional[list[str]] = None,
    correlation_id: Optional[str] = None,
    db_session: Optional[Session] = None,
) -> QuestInteractionMutationResult:
    with task_transaction(db_session) as session:
        event_kind = 'quest.collaborator_set' if active else 'quest.collaborator_removed'
        request_payload = {
            'quest_id': quest_id,
            'agent_node_id': agent_node_id,
            'role': str(role or 'advisor'),
            'status': str(status or 'active'),
            'is_primary_companion': bool(is_primary_companion),
            'capability_scope': sorted(str(item) for item in capability_scope or []),
        }
        replay, revision, fingerprint = _mutation_context(
            session,
            account_node_id=account_node_id,
            actor=actor,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
            permission=TASK_UPDATE,
            kind=event_kind,
            request_payload=request_payload,
        )
        if replay is not None:
            return replay
        _readable_quest(session, quest_id=quest_id, actor=actor)
        load_node_ref(session, node_id=int(agent_node_id), expected_type_code='npc_agent')
        if not can_read_semantic_node(session, node_id=int(agent_node_id), actor=actor):
            raise ReferenceNotFound(f'agent {agent_node_id} not found')
        existing = _active_relationship(
            session, source_id=quest_id, target_id=agent_node_id, type_code='ASSISTED_BY'
        )
        existing_attrs = _relationship_attributes(session, existing) if existing is not None else {}
        desired_attrs = {
            'role': str(role or 'advisor'),
            'status': str(status or 'active'),
            'is_primary_companion': bool(is_primary_companion),
            'capability_scope': sorted(str(item) for item in capability_scope or []),
        }
        same_active_configuration = existing is not None and all(
            existing_attrs.get(key) == value for key, value in desired_attrs.items()
        )
        changed = (active and not same_active_configuration) or (not active and existing is not None)
        if active and same_active_configuration:
            return _unchanged_result(
                session,
                account_node_id=account_node_id,
                current_revision=revision,
                relationship_id=existing,
            )
        if not active and existing is None:
            return _unchanged_result(session, account_node_id=account_node_id, current_revision=revision)
        if active:
            if is_primary_companion:
                session.execute(
                    text(
                        """
                        UPDATE relationships
                           SET attributes = jsonb_set(
                               COALESCE(attributes, '{}'::jsonb),
                               '{is_primary_companion}',
                               'false'::jsonb,
                               TRUE
                           ), updated_at = now()
                         WHERE source_id = :quest_id
                           AND type_code = 'ASSISTED_BY'
                           AND is_active = TRUE
                        """
                    ),
                    {'quest_id': int(quest_id)},
                )
            attrs = _edge_metadata(
                actor,
                correlation_id,
                **desired_attrs,
                valid_from=datetime.now(tz=timezone.utc).isoformat(),
                valid_to=None,
            )
            if existing is not None:
                session.execute(
                    text(
                        """
                        UPDATE relationships
                           SET is_active = FALSE,
                               attributes = COALESCE(attributes, '{}'::jsonb)
                                   || CAST(:metadata AS jsonb),
                               updated_at = now()
                         WHERE id = :relationship_id
                        """
                    ),
                    {
                        'relationship_id': existing,
                        'metadata': json.dumps(
                            _edge_metadata(
                                actor,
                                correlation_id,
                                status='superseded',
                                valid_to=datetime.now(tz=timezone.utc).isoformat(),
                            ),
                            ensure_ascii=False,
                        ),
                    },
                )
                session.execute(
                    text("""
                        UPDATE agent_conversation_thread
                           SET archived_at = COALESCE(archived_at, now()),
                               archive_reason = COALESCE(archive_reason, 'collaboration_replaced')
                         WHERE collaboration_relationship_id = :relationship_id
                           AND archived_at IS NULL
                    """),
                    {'relationship_id': existing},
                )
            existing = insert_relationship(
                session,
                source_id=quest_id,
                target_id=agent_node_id,
                type_code='ASSISTED_BY',
                attributes=attrs,
                tags=['quest_collaboration'],
            )
        elif existing is not None:
            session.execute(
                text(
                    """
                    UPDATE relationships
                       SET is_active = FALSE,
                           attributes = COALESCE(attributes, '{}'::jsonb)
                               || CAST(:metadata AS jsonb),
                           updated_at = now()
                     WHERE id = :relationship_id
                    """
                ),
                {
                    'relationship_id': existing,
                    'metadata': json.dumps(
                        _edge_metadata(
                            actor,
                            correlation_id,
                            status='ended',
                            valid_to=datetime.now(tz=timezone.utc).isoformat(),
                        ),
                        ensure_ascii=False,
                    ),
                },
            )
            session.execute(
                text("""
                    UPDATE agent_conversation_thread
                       SET archived_at = COALESCE(archived_at, now()),
                           archive_reason = COALESCE(archive_reason, 'collaboration_ended')
                     WHERE collaboration_relationship_id = :relationship_id
                       AND archived_at IS NULL
                """),
                {'relationship_id': existing},
            )
        return _append_event(
            session,
            account_node_id=account_node_id,
            current_revision=revision,
            kind=event_kind,
            target_node_id=agent_node_id,
            actor=actor,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            payload={
                'changed': changed,
                'quest_id': quest_id,
                'agent_node_id': agent_node_id,
                'relationship_id': existing,
            },
            request_fingerprint=fingerprint,
        )


def set_situation_attention(
    *,
    account_node_id: int,
    situation_id: int,
    attention: str,
    expected_revision: str,
    idempotency_key: str,
    actor: Principal,
    correlation_id: Optional[str] = None,
    snoozed_until: Optional[str] = None,
    db_session: Optional[Session] = None,
) -> QuestInteractionMutationResult:
    """Persist account-scoped Pulse attention without changing Situation state."""
    clean_attention = str(attention or '').strip().lower()
    if clean_attention not in {'seen', 'snoozed', 'ui_dismissed', 'reset'}:
        raise PreconditionFailed('attention must be seen, snoozed, ui_dismissed, or reset')
    parsed_snooze = None
    if clean_attention == 'snoozed':
        try:
            parsed_snooze = datetime.fromisoformat(str(snoozed_until or '').replace('Z', '+00:00'))
        except ValueError as exc:
            raise PreconditionFailed('snoozed_until must be an ISO-8601 datetime') from exc
        if parsed_snooze.tzinfo is None or parsed_snooze <= datetime.now(tz=timezone.utc):
            raise PreconditionFailed('snoozed_until must be a future timezone-aware datetime')
    with task_transaction(db_session) as session:
        load_node_ref(session, node_id=int(situation_id), expected_type_code='situation')
        if not can_read_semantic_node(session, node_id=int(situation_id), actor=actor):
            raise ReferenceNotFound(f'situation {situation_id} not found')
        replay, revision, fingerprint = _mutation_context(
            session,
            account_node_id=account_node_id,
            actor=actor,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
            kind=f'situation_attention.{clean_attention}',
            request_payload={'situation_id': int(situation_id), 'attention': clean_attention, 'snoozed_until': snoozed_until},
        )
        if replay is not None:
            return replay
        row = session.execute(
            text("""
                SELECT seen_at, snoozed_until, ui_dismissed_at
                  FROM situation_attention
                 WHERE account_node_id = :account_id AND situation_node_id = :situation_id
                 FOR UPDATE
            """),
            {'account_id': int(account_node_id), 'situation_id': int(situation_id)},
        ).first()
        now = datetime.now(tz=timezone.utc)
        values = {
            'seen_at': now if clean_attention == 'seen' else None,
            'snoozed_until': parsed_snooze if clean_attention == 'snoozed' else None,
            'ui_dismissed_at': now if clean_attention == 'ui_dismissed' else None,
        }
        if row is not None and all(
            (getattr(row, key) is None and value is None)
            or (getattr(row, key) is not None and value is not None and (
                getattr(row, key) == value if key != 'seen_at' and key != 'ui_dismissed_at'
                else clean_attention in {'seen', 'ui_dismissed'}
            ))
            for key, value in values.items()
        ):
            return _unchanged_result(session, account_node_id=account_node_id, current_revision=revision)
        session.execute(
            text("""
                INSERT INTO situation_attention
                    (account_node_id, situation_node_id, seen_at, snoozed_until, ui_dismissed_at, updated_at)
                VALUES (:account_id, :situation_id, :seen_at, :snoozed_until, :ui_dismissed_at, now())
                ON CONFLICT (account_node_id, situation_node_id) DO UPDATE SET
                    seen_at = EXCLUDED.seen_at,
                    snoozed_until = EXCLUDED.snoozed_until,
                    ui_dismissed_at = EXCLUDED.ui_dismissed_at,
                    updated_at = now()
            """),
            {'account_id': int(account_node_id), 'situation_id': int(situation_id), **values},
        )
        return _append_event(
            session,
            account_node_id=account_node_id,
            current_revision=revision,
            kind=f'situation_attention.{clean_attention}',
            target_node_id=situation_id,
            actor=actor,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            payload={'changed': True, 'situation_id': int(situation_id), 'attention': clean_attention},
            request_fingerprint=fingerprint,
        )


def new_correlation_id() -> str:
    return f'quest-interaction-{uuid.uuid4()}'


__all__ = [
    'QuestInteractionMutationResult',
    'focus_objective',
    'new_correlation_id',
    'record_projection_change',
    'read_projection_cursor',
    'set_clue_pin',
    'set_collaborator',
    'set_situation_attention',
    'track_quest',
    'untrack_quest',
]
