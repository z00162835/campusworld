"""R1 semantic shell for Situation → Goal → Quest → task objectives."""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.task.errors import PreconditionFailed, ReferenceNotFound, WorkflowDefinitionNotFound
from app.services.task.permissions import Principal, TASK_ADMIN
from app.services.task.task_state_machine import insert_relationship, load_node_ref, task_transaction

logger = logging.getLogger("campusworld.task.quest_semantic")

_SITUATION_TRIGGER_KINDS = frozenset({'hard_rule', 'weak_experience', 'manual', 'mixed'})
_SITUATION_SEVERITIES = frozenset({'low', 'medium', 'high', 'critical'})
_GOAL_PRIORITIES = frozenset({'low', 'normal', 'high', 'urgent'})
_QUEST_RISK_LEVELS = frozenset({'low', 'normal', 'high', 'critical'})
_QUEST_SUCCESS_OBJECTIVE_STATES = frozenset({'done'})
_QUEST_FAILED_OBJECTIVE_STATES = frozenset({'failed'})
_QUEST_CANCELLED_OBJECTIVE_STATES = frozenset({'cancelled'})
_QUEST_TERMINAL_OBJECTIVE_STATES = _QUEST_SUCCESS_OBJECTIVE_STATES | _QUEST_FAILED_OBJECTIVE_STATES | _QUEST_CANCELLED_OBJECTIVE_STATES
SEMANTIC_NODE_INITIAL_STATES = {
    'situation': 'asserted',
    'goal': 'proposed',
    'quest': 'draft',
}


@dataclass(frozen=True)
class SemanticNodeResult:
    node_id: int
    type_code: str
    title: str
    attributes: Dict[str, Any]


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _non_empty_list(values: Optional[List[str]]) -> List[str]:
    return [str(v).strip() for v in values or [] if str(v).strip()]


def split_semantic_ref(ref: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Parse ``namespace:key@version`` refs."""
    text_ref = str(ref or '').strip()
    if not text_ref:
        return None, None, None
    version: Optional[str] = None
    base = text_ref
    if '@' in base:
        base, version = base.rsplit('@', 1)
        version = version.strip() or None
    namespace: Optional[str] = None
    key = base.strip()
    if ':' in key:
        namespace, key = key.split(':', 1)
        namespace = namespace.strip() or None
        key = key.strip()
    return namespace, key or None, version


def _is_version_pinned_semantic_ref(ref: str) -> bool:
    namespace, key, version = split_semantic_ref(ref)
    return bool(namespace and key and version)


def _require_version_pinned_refs(refs: Optional[List[str]], *, field_name: str) -> None:
    for semantic_ref in _non_empty_list(refs):
        if not _is_version_pinned_semantic_ref(semantic_ref):
            raise PreconditionFailed(f'{field_name} must use namespace:key@version refs: {semantic_ref}')


def _row_attributes(row: Any) -> Dict[str, Any]:
    attrs = row.attributes
    if isinstance(attrs, dict):
        return attrs
    try:
        loaded = json.loads(attrs or '{}')
    except (TypeError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def summarize_objective_progress(states: List[str]) -> Dict[str, int]:
    total = len(states)
    succeeded = sum(1 for state in states if state in _QUEST_SUCCESS_OBJECTIVE_STATES)
    failed = sum(1 for state in states if state in _QUEST_FAILED_OBJECTIVE_STATES)
    cancelled = sum(1 for state in states if state in _QUEST_CANCELLED_OBJECTIVE_STATES)
    terminal = succeeded + failed + cancelled
    return {
        'total_objectives': total,
        'terminal_objectives': terminal,
        'completed_objectives': succeeded,
        'succeeded_objectives': succeeded,
        'failed_objectives': failed,
        'cancelled_objectives': cancelled,
        'percent': int(round((terminal / total) * 100)) if total else 0,
        'success_percent': int(round((succeeded / total) * 100)) if total else 0,
    }


def explicit_node_id_ref(ref: str) -> Optional[int]:
    text_ref = str(ref or '').strip()
    if not text_ref:
        return None
    if text_ref.isdigit():
        return int(text_ref)
    lowered = text_ref.lower()
    if lowered.startswith('node:') and lowered[5:].isdigit():
        return int(lowered[5:])
    if lowered.startswith('#') and lowered[1:].isdigit():
        return int(lowered[1:])
    return None


def resolve_semantic_node_ref(session: Session, ref: str) -> Optional[int]:
    """Resolve a pinned semantic ref to an active graph node when possible.

    R1 keeps refs as durable strings. This helper opportunistically bridges
    those refs back into the graph when an existing node advertises a matching
    ref/key, without making unresolved refs an error.
    """
    text_ref = str(ref or '').strip()
    if not text_ref:
        return None

    explicit_id = explicit_node_id_ref(text_ref)
    if explicit_id is not None:
        try:
            return int(load_node_ref(session, node_id=explicit_id)['id'])
        except ReferenceNotFound:
            return None

    namespace, key, version = split_semantic_ref(text_ref)
    rows = session.execute(
        text(
            """
            SELECT id, type_code, name, attributes
              FROM nodes
             WHERE is_active = TRUE
               AND (
                    attributes->>'semantic_ref' = :ref
                 OR attributes->>'ref' = :ref
                 OR attributes->>'source_ref' = :ref
                 OR attributes->>'external_ref' = :ref
                 OR (:namespace IS NULL AND attributes->>'key' = :ref)
                 OR (:namespace IS NULL AND attributes->>'code' = :ref)
                 OR (
                        :key IS NOT NULL
                    AND (attributes->>'key' = :key OR attributes->>'code' = :key)
                    AND (:namespace IS NULL OR type_code = :namespace)
                    AND (
                           :version IS NULL
                        OR attributes->>'version' = :version
                        OR attributes->>'ref_version' = :version
                    )
                 )
               )
             ORDER BY id ASC
             LIMIT 20
            """
        ),
        {'ref': text_ref, 'namespace': namespace, 'key': key, 'version': version},
    ).all()
    if not rows:
        logger.debug('semantic_ref.resolve.unresolved', extra={'semantic_ref': text_ref})
        return None
    if namespace:
        exact_fields = ('semantic_ref', 'ref', 'source_ref', 'external_ref')
        exact_candidates = []
        for row in rows:
            attrs = _row_attributes(row)
            if any(str(attrs.get(field) or '') == text_ref for field in exact_fields):
                exact_candidates.append(row)
        if exact_candidates:
            if len(exact_candidates) > 1:
                logger.debug(
                    'semantic_ref.resolve.ambiguous',
                    extra={
                        'semantic_ref': text_ref,
                        'candidate_ids': [int(row.id) for row in exact_candidates],
                        'selected_id': int(exact_candidates[0].id),
                    },
                )
            return int(exact_candidates[0].id)
        namespace_candidates = [row for row in rows if str(row.type_code) == namespace]
        if namespace_candidates:
            if len(namespace_candidates) > 1:
                logger.debug(
                    'semantic_ref.resolve.ambiguous',
                    extra={
                        'semantic_ref': text_ref,
                        'candidate_ids': [int(row.id) for row in namespace_candidates],
                        'selected_id': int(namespace_candidates[0].id),
                    },
                )
            return int(namespace_candidates[0].id)
        logger.debug('semantic_ref.resolve.unresolved', extra={'semantic_ref': text_ref, 'namespace': namespace})
        return None
    if len(rows) > 1:
        logger.debug(
            'semantic_ref.resolve.ambiguous',
            extra={
                'semantic_ref': text_ref,
                'candidate_ids': [int(row.id) for row in rows],
                'selected_id': int(rows[0].id),
            },
        )
    return int(rows[0].id)


def _insert_resolved_ref_edges(
    session: Session,
    *,
    source_id: int,
    refs: Optional[List[str]],
    type_code: str,
    ref_kind: str,
) -> None:
    seen: Set[Tuple[str, int]] = set()
    for semantic_ref in _non_empty_list(refs):
        target_id = resolve_semantic_node_ref(session, semantic_ref)
        if target_id is None:
            logger.debug(
                'semantic_ref.edge.unresolved',
                extra={
                    'source_id': int(source_id),
                    'relationship_type': type_code,
                    'ref_kind': ref_kind,
                    'semantic_ref': semantic_ref,
                },
            )
            continue
        edge_key = (type_code, target_id)
        if edge_key in seen:
            continue
        seen.add(edge_key)
        insert_relationship(
            session,
            source_id=source_id,
            target_id=target_id,
            type_code=type_code,
            attributes={'semantic_ref': semantic_ref, 'ref_kind': ref_kind},
            tags=['semantic_ref'],
        )


def validate_situation_semantics(
    *,
    assertion: Optional[str],
    trigger_kind: str,
    fact_refs: Optional[List[str]] = None,
    evidence_refs: Optional[List[str]] = None,
    rule_refs: Optional[List[str]] = None,
    experience_refs: Optional[List[str]] = None,
    inference_trace_summary: Optional[str] = None,
) -> None:
    """Validate R1 Situation assertion and trigger provenance invariants."""
    assertion_text = str(assertion or '').strip()
    if not assertion_text:
        raise PreconditionFailed('situation.assertion is required')
    if trigger_kind not in _SITUATION_TRIGGER_KINDS:
        raise PreconditionFailed(f'situation.trigger_kind must be one of {sorted(_SITUATION_TRIGGER_KINDS)}')

    facts = _non_empty_list(fact_refs)
    evidence = _non_empty_list(evidence_refs)
    rules = _non_empty_list(rule_refs)
    experiences = _non_empty_list(experience_refs)
    inference = str(inference_trace_summary or '').strip()

    if trigger_kind != 'manual' and not facts and not evidence:
        raise PreconditionFailed('non-manual situation requires at least one fact_ref or evidence_ref')
    if trigger_kind == 'hard_rule' and not rules:
        raise PreconditionFailed("trigger_kind='hard_rule' requires at least one rule_ref")
    if rules:
        _require_version_pinned_refs(rules, field_name='situation.rule_refs')
    if trigger_kind == 'weak_experience' and not experiences and not inference:
        raise PreconditionFailed("trigger_kind='weak_experience' requires experience_ref or inference_trace_summary")
    if trigger_kind == 'mixed':
        if not rules:
            raise PreconditionFailed("trigger_kind='mixed' requires at least one rule_ref")
        if not experiences and not inference:
            raise PreconditionFailed("trigger_kind='mixed' requires experience_ref or inference_trace_summary")


def _load_node_type_id(session: Session, *, type_code: str) -> int:
    row = session.execute(text('SELECT id FROM node_types WHERE type_code = :type_code'), {'type_code': type_code}).first()
    if row is None:
        raise WorkflowDefinitionNotFound(f"node_types.type_code='{type_code}' missing; run schema migration first")
    return int(row[0])


def _insert_node(
    session: Session,
    *,
    type_code: str,
    title: str,
    attributes: Dict[str, Any],
    tags: Optional[List[str]] = None,
) -> int:
    type_id = _load_node_type_id(session, type_code=type_code)
    row = session.execute(
        text(
            """
            INSERT INTO nodes (uuid, type_id, type_code, name, description,
                               attributes, tags, is_active, is_public)
            VALUES (:uuid, :type_id, :type_code, :name, :description,
                    CAST(:attrs AS jsonb), CAST(:tags AS jsonb), TRUE, FALSE)
            RETURNING id
            """
        ),
        {
            'uuid': uuid.uuid4(),
            'type_id': type_id,
            'type_code': type_code,
            'name': title[:255],
            'description': None,
            'attrs': json.dumps(attributes, ensure_ascii=False),
            'tags': json.dumps(tags or [type_code], ensure_ascii=False),
        },
    ).first()
    return int(row[0])


def _actor_provenance(actor: Principal) -> Dict[str, Any]:
    return {'principal_id': actor.id if actor.kind != 'system' else None, 'principal_kind': actor.kind}


def _insert_owner_edge(session: Session, *, node_id: int, actor: Principal) -> None:
    if actor.kind == 'system':
        return
    load_node_ref(session, node_id=actor.id)
    insert_relationship(
        session,
        source_id=node_id,
        target_id=actor.id,
        type_code='OWNED_BY',
        attributes={'principal_kind': actor.kind},
    )


def _can_read_all_semantic_nodes(actor: Principal) -> bool:
    return actor.kind == 'system' or actor.has_permission(TASK_ADMIN)


def _can_read_semantic_node(session: Session, *, node_id: int, actor: Principal) -> bool:
    if _can_read_all_semantic_nodes(actor):
        return True
    row = session.execute(
        text(
            """
            SELECT 1
              FROM relationships r
             WHERE r.source_id = :node_id
               AND r.target_id = :actor_id
               AND r.type_code = 'OWNED_BY'
               AND r.is_active = TRUE
               AND COALESCE(r.attributes->>'principal_kind', :actor_kind) = :actor_kind
             LIMIT 1
            """
        ),
        {'node_id': int(node_id), 'actor_id': int(actor.id), 'actor_kind': actor.kind},
    ).first()
    return row is not None


def create_situation(
    *,
    title: str,
    assertion: str,
    actor: Principal,
    subject_id: Optional[int] = None,
    trigger_kind: str = 'manual',
    trigger_summary: Optional[str] = None,
    fact_refs: Optional[List[str]] = None,
    evidence_refs: Optional[List[str]] = None,
    rule_refs: Optional[List[str]] = None,
    experience_refs: Optional[List[str]] = None,
    inference_trace_summary: Optional[str] = None,
    confidence: Optional[float] = None,
    severity: str = 'medium',
    business_impact: Optional[str] = None,
    temporal_scope: Optional[Dict[str, Any]] = None,
    db_session: Optional[Session] = None,
) -> SemanticNodeResult:
    if severity not in _SITUATION_SEVERITIES:
        raise PreconditionFailed(f'situation.severity must be one of {sorted(_SITUATION_SEVERITIES)}')
    if confidence is not None and not (0 <= float(confidence) <= 1):
        raise PreconditionFailed('situation.confidence must be between 0 and 1')
    validate_situation_semantics(
        assertion=assertion,
        trigger_kind=trigger_kind,
        fact_refs=fact_refs,
        evidence_refs=evidence_refs,
        rule_refs=rule_refs,
        experience_refs=experience_refs,
        inference_trace_summary=inference_trace_summary,
    )
    with task_transaction(db_session) as session:
        if subject_id is not None:
            load_node_ref(session, node_id=int(subject_id))
        attrs: Dict[str, Any] = {
            'current_state': SEMANTIC_NODE_INITIAL_STATES['situation'],
            'state_version': 1,
            'title': title,
            'assertion': assertion,
            'subject_ref': int(subject_id) if subject_id is not None else None,
            'trigger_kind': trigger_kind,
            'trigger_summary': trigger_summary,
            'fact_refs': _non_empty_list(fact_refs),
            'evidence_refs': _non_empty_list(evidence_refs),
            'rule_refs': _non_empty_list(rule_refs),
            'experience_refs': _non_empty_list(experience_refs),
            'inference_trace_summary': str(inference_trace_summary or '').strip() or None,
            'confidence': confidence,
            'severity': severity,
            'business_impact': business_impact,
            'temporal_scope': temporal_scope or {},
            'actor_provenance': _actor_provenance(actor),
            'asserted_at': _now_iso(),
        }
        situation_id = _insert_node(session, type_code='situation', title=title, attributes=attrs)
        _insert_owner_edge(session, node_id=situation_id, actor=actor)
        if subject_id is not None:
            insert_relationship(session, source_id=situation_id, target_id=int(subject_id), type_code='ABOUT')
        _insert_resolved_ref_edges(session, source_id=situation_id, refs=attrs['fact_refs'], type_code='SUPPORTED_BY', ref_kind='fact')
        _insert_resolved_ref_edges(session, source_id=situation_id, refs=attrs['evidence_refs'], type_code='SUPPORTED_BY', ref_kind='evidence')
        _insert_resolved_ref_edges(session, source_id=situation_id, refs=attrs['rule_refs'], type_code='TRIGGERED_BY_RULE', ref_kind='rule')
        _insert_resolved_ref_edges(session, source_id=situation_id, refs=attrs['experience_refs'], type_code='TRIGGERED_BY_EXPERIENCE', ref_kind='experience')
        return SemanticNodeResult(node_id=situation_id, type_code='situation', title=title, attributes=attrs)


def create_goal(
    *,
    title: str,
    situation_id: int,
    actor: Principal,
    desired_state: Optional[Any] = None,
    constraints: Optional[Dict[str, Any]] = None,
    priority: str = 'normal',
    deadline_at: Optional[str] = None,
    owner_principal: Optional[Dict[str, Any]] = None,
    acceptance_summary: Optional[str] = None,
    db_session: Optional[Session] = None,
) -> SemanticNodeResult:
    if priority not in _GOAL_PRIORITIES:
        raise PreconditionFailed(f'goal.priority must be one of {sorted(_GOAL_PRIORITIES)}')
    if desired_state is None or (isinstance(desired_state, str) and not desired_state.strip()):
        raise PreconditionFailed('goal.desired_state is required')
    with task_transaction(db_session) as session:
        load_node_ref(session, node_id=int(situation_id), expected_type_code='situation')
        attrs: Dict[str, Any] = {
            'current_state': SEMANTIC_NODE_INITIAL_STATES['goal'],
            'state_version': 1,
            'title': title,
            'desired_state': desired_state,
            'constraints': constraints or {},
            'priority': priority,
            'deadline_at': deadline_at,
            'owner_principal': owner_principal or _actor_provenance(actor),
            'acceptance_summary': acceptance_summary,
            'situation_id': int(situation_id),
            'created_by': _actor_provenance(actor),
            'created_at': _now_iso(),
        }
        goal_id = _insert_node(session, type_code='goal', title=title, attributes=attrs)
        _insert_owner_edge(session, node_id=goal_id, actor=actor)
        insert_relationship(session, source_id=goal_id, target_id=int(situation_id), type_code='GOAL_FOR')
        insert_relationship(session, source_id=int(situation_id), target_id=goal_id, type_code='RAISES_GOAL')
        return SemanticNodeResult(node_id=goal_id, type_code='goal', title=title, attributes=attrs)


def create_quest(
    *,
    title: str,
    situation_id: int,
    goal_id: int,
    actor: Principal,
    risk_level: str = 'normal',
    quest_ref: Optional[Dict[str, Any]] = None,
    plan_graph_summary: Optional[Any] = None,
    policy_refs: Optional[List[str]] = None,
    process_refs: Optional[List[str]] = None,
    quality_refs: Optional[List[str]] = None,
    case_refs: Optional[List[str]] = None,
    db_session: Optional[Session] = None,
) -> SemanticNodeResult:
    if risk_level not in _QUEST_RISK_LEVELS:
        raise PreconditionFailed(f'quest.risk_level must be one of {sorted(_QUEST_RISK_LEVELS)}')
    _require_version_pinned_refs(policy_refs, field_name='quest.policy_refs')
    _require_version_pinned_refs(process_refs, field_name='quest.process_refs')
    _require_version_pinned_refs(quality_refs, field_name='quest.quality_refs')
    with task_transaction(db_session) as session:
        load_node_ref(session, node_id=int(situation_id), expected_type_code='situation')
        goal = load_node_ref(session, node_id=int(goal_id), expected_type_code='goal')
        if int(goal['attributes'].get('situation_id') or 0) != int(situation_id):
            raise PreconditionFailed('quest.goal must belong to quest.situation')
        attrs: Dict[str, Any] = {
            'current_state': SEMANTIC_NODE_INITIAL_STATES['quest'],
            'state_version': 1,
            'title': title,
            'situation_id': int(situation_id),
            'goal_id': int(goal_id),
            'risk_level': risk_level,
            'quest_ref': quest_ref,
            'plan_graph_summary': plan_graph_summary,
            'policy_refs': _non_empty_list(policy_refs),
            'process_refs': _non_empty_list(process_refs),
            'quality_refs': _non_empty_list(quality_refs),
            'case_refs': _non_empty_list(case_refs),
            'outcome_summary': {},
            'created_by': _actor_provenance(actor),
            'created_at': _now_iso(),
        }
        quest_id = _insert_node(session, type_code='quest', title=title, attributes=attrs)
        _insert_owner_edge(session, node_id=quest_id, actor=actor)
        insert_relationship(session, source_id=quest_id, target_id=int(situation_id), type_code='RESPONDS_TO')
        insert_relationship(session, source_id=quest_id, target_id=int(goal_id), type_code='PURSUES')
        insert_relationship(session, source_id=int(goal_id), target_id=quest_id, type_code='REALIZED_BY')
        _insert_resolved_ref_edges(session, source_id=quest_id, refs=attrs['policy_refs'], type_code='GOVERNED_BY', ref_kind='policy')
        _insert_resolved_ref_edges(session, source_id=quest_id, refs=attrs['process_refs'], type_code='GUIDED_BY', ref_kind='process')
        _insert_resolved_ref_edges(session, source_id=quest_id, refs=attrs['quality_refs'], type_code='MEASURED_BY', ref_kind='quality')
        _insert_resolved_ref_edges(session, source_id=quest_id, refs=attrs['case_refs'], type_code='INFORMED_BY', ref_kind='case')
        return SemanticNodeResult(node_id=quest_id, type_code='quest', title=title, attributes=attrs)


def list_nodes(*, type_code: str, actor: Principal, limit: int = 20, db_session: Optional[Session] = None) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit), 200))
    with task_transaction(db_session) as session:
        owner_clause = ''
        params: Dict[str, Any] = {'type_code': type_code, 'limit': limit}
        if not _can_read_all_semantic_nodes(actor):
            owner_clause = """
                   AND EXISTS (
                        SELECT 1
                          FROM relationships own
                         WHERE own.source_id = n.id
                           AND own.target_id = :actor_id
                           AND own.type_code = 'OWNED_BY'
                           AND own.is_active = TRUE
                           AND COALESCE(own.attributes->>'principal_kind', :actor_kind) = :actor_kind
                   )
            """
            params.update({'actor_id': int(actor.id), 'actor_kind': actor.kind})
        rows = session.execute(
            text(
                f"""
                SELECT id, name, attributes, created_at
                  FROM nodes n
                 WHERE n.type_code = :type_code
                   AND n.is_active = TRUE
                   {owner_clause}
                 ORDER BY created_at DESC, id DESC
                 LIMIT :limit
                """
            ),
            params,
        ).all()
        return [
            {
                'id': int(row.id),
                'title': row.name,
                'attributes': row.attributes if isinstance(row.attributes, dict) else json.loads(row.attributes or '{}'),
                'created_at': row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]


def show_node(*, node_id: int, type_code: str, actor: Principal, db_session: Optional[Session] = None) -> Dict[str, Any]:
    with task_transaction(db_session) as session:
        node = load_node_ref(session, node_id=int(node_id), expected_type_code=type_code)
        if not _can_read_semantic_node(session, node_id=int(node_id), actor=actor):
            raise ReferenceNotFound(f'{type_code} {node_id} not found')
        return {'id': node['id'], 'type_code': node['type_code'], 'title': node['name'], 'attributes': node['attributes']}


def show_quest(*, quest_id: int, actor: Principal, db_session: Optional[Session] = None) -> Dict[str, Any]:
    with task_transaction(db_session) as session:
        quest = load_node_ref(session, node_id=int(quest_id), expected_type_code='quest')
        if not _can_read_semantic_node(session, node_id=int(quest_id), actor=actor):
            raise ReferenceNotFound(f'quest {quest_id} not found')
        attrs = quest['attributes']
        situation = load_node_ref(session, node_id=int(attrs.get('situation_id')), expected_type_code='situation')
        goal = load_node_ref(session, node_id=int(attrs.get('goal_id')), expected_type_code='goal')
        objectives = session.execute(
            text(
                """
                SELECT t.id, t.name, t.attributes
                  FROM relationships r
                  JOIN nodes t ON t.id = r.target_id
                 WHERE r.source_id = :quest_id
                   AND r.type_code = 'HAS_OBJECTIVE'
                   AND r.is_active = TRUE
                   AND t.type_code = 'task'
                   AND t.is_active = TRUE
                 ORDER BY t.created_at ASC, t.id ASC
                """
            ),
            {'quest_id': int(quest_id)},
        ).all()
        objective_items: List[Dict[str, Any]] = []
        objective_states: List[str] = []
        for row in objectives:
            task_attrs = row.attributes if isinstance(row.attributes, dict) else json.loads(row.attributes or '{}')
            state = str(task_attrs.get('current_state') or '')
            objective_states.append(state)
            objective_items.append(
                {
                    'task_id': int(row.id),
                    'title': row.name,
                    'current_state': state,
                    'objective_kind': task_attrs.get('objective_kind'),
                    'required_capabilities': task_attrs.get('required_capabilities') or [],
                }
            )
        progress = summarize_objective_progress(objective_states)
        return {
            'quest': {'id': quest['id'], 'title': quest['name'], 'attributes': {**attrs, 'progress': progress}},
            'situation': {
                'id': situation['id'],
                'title': situation['name'],
                'assertion': situation['attributes'].get('assertion'),
                'trigger_kind': situation['attributes'].get('trigger_kind'),
                'trigger_summary': situation['attributes'].get('trigger_summary'),
                'fact_refs': situation['attributes'].get('fact_refs') or [],
                'evidence_refs': situation['attributes'].get('evidence_refs') or [],
                'rule_refs': situation['attributes'].get('rule_refs') or [],
                'experience_refs': situation['attributes'].get('experience_refs') or [],
                'inference_trace_summary': situation['attributes'].get('inference_trace_summary'),
            },
            'goal': {'id': goal['id'], 'title': goal['name'], 'attributes': goal['attributes']},
            'objectives': objective_items,
            'progress': progress,
        }


__all__ = [
    'SemanticNodeResult',
    'SEMANTIC_NODE_INITIAL_STATES',
    'explicit_node_id_ref',
    'resolve_semantic_node_ref',
    'split_semantic_ref',
    'create_situation',
    'create_goal',
    'create_quest',
    'list_nodes',
    'show_node',
    'show_quest',
    'summarize_objective_progress',
    'validate_situation_semantics',
]
