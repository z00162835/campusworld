"""R1 semantic shell for Situation → Goal → Quest → task objectives."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.task.errors import PreconditionFailed, ReferenceNotFound, WorkflowDefinitionNotFound
from app.services.task.permissions import Principal
from app.services.task.task_state_machine import _insert_relationship, _load_node_ref, _transaction

_SITUATION_TRIGGER_KINDS = frozenset({'hard_rule', 'weak_experience', 'manual', 'mixed'})
_SITUATION_SEVERITIES = frozenset({'low', 'medium', 'high', 'critical'})
_GOAL_PRIORITIES = frozenset({'low', 'normal', 'high', 'urgent'})
_QUEST_TERMINAL_OBJECTIVE_STATES = frozenset({'done', 'failed', 'cancelled'})


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
    with _transaction(db_session) as session:
        if subject_id is not None:
            _load_node_ref(session, node_id=int(subject_id))
        attrs: Dict[str, Any] = {
            'current_state': 'asserted',
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
        if subject_id is not None:
            _insert_relationship(session, source_id=situation_id, target_id=int(subject_id), type_code='ABOUT')
        return SemanticNodeResult(node_id=situation_id, type_code='situation', title=title, attributes=attrs)


def create_goal(
    *,
    title: str,
    situation_id: int,
    actor: Principal,
    desired_state: Optional[str] = None,
    constraints: Optional[Dict[str, Any]] = None,
    priority: str = 'normal',
    deadline_at: Optional[str] = None,
    owner_principal: Optional[Dict[str, Any]] = None,
    acceptance_summary: Optional[str] = None,
    db_session: Optional[Session] = None,
) -> SemanticNodeResult:
    if priority not in _GOAL_PRIORITIES:
        raise PreconditionFailed(f'goal.priority must be one of {sorted(_GOAL_PRIORITIES)}')
    with _transaction(db_session) as session:
        _load_node_ref(session, node_id=int(situation_id), expected_type_code='situation')
        attrs: Dict[str, Any] = {
            'current_state': 'draft',
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
        _insert_relationship(session, source_id=goal_id, target_id=int(situation_id), type_code='GOAL_FOR')
        _insert_relationship(session, source_id=int(situation_id), target_id=goal_id, type_code='RAISES_GOAL')
        return SemanticNodeResult(node_id=goal_id, type_code='goal', title=title, attributes=attrs)


def create_quest(
    *,
    title: str,
    situation_id: int,
    goal_id: int,
    actor: Principal,
    risk_level: str = 'normal',
    plan_graph_summary: Optional[str] = None,
    policy_refs: Optional[List[str]] = None,
    process_refs: Optional[List[str]] = None,
    quality_refs: Optional[List[str]] = None,
    case_refs: Optional[List[str]] = None,
    db_session: Optional[Session] = None,
) -> SemanticNodeResult:
    with _transaction(db_session) as session:
        _load_node_ref(session, node_id=int(situation_id), expected_type_code='situation')
        goal = _load_node_ref(session, node_id=int(goal_id), expected_type_code='goal')
        if int(goal['attributes'].get('situation_id') or 0) != int(situation_id):
            raise PreconditionFailed('quest.goal must belong to quest.situation')
        attrs: Dict[str, Any] = {
            'current_state': 'draft',
            'state_version': 1,
            'title': title,
            'situation_id': int(situation_id),
            'goal_id': int(goal_id),
            'risk_level': risk_level,
            'progress': {'total_objectives': 0, 'completed_objectives': 0, 'percent': 0},
            'plan_graph_summary': plan_graph_summary,
            'policy_refs': _non_empty_list(policy_refs),
            'process_refs': _non_empty_list(process_refs),
            'quality_refs': _non_empty_list(quality_refs),
            'case_refs': _non_empty_list(case_refs),
            'created_by': _actor_provenance(actor),
            'created_at': _now_iso(),
        }
        quest_id = _insert_node(session, type_code='quest', title=title, attributes=attrs)
        _insert_relationship(session, source_id=quest_id, target_id=int(situation_id), type_code='RESPONDS_TO')
        _insert_relationship(session, source_id=quest_id, target_id=int(goal_id), type_code='PURSUES')
        return SemanticNodeResult(node_id=quest_id, type_code='quest', title=title, attributes=attrs)


def list_nodes(*, type_code: str, limit: int = 20, db_session: Optional[Session] = None) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit), 200))
    with _transaction(db_session) as session:
        rows = session.execute(
            text(
                """
                SELECT id, name, attributes, created_at
                  FROM nodes
                 WHERE type_code = :type_code
                   AND is_active = TRUE
                 ORDER BY created_at DESC, id DESC
                 LIMIT :limit
                """
            ),
            {'type_code': type_code, 'limit': limit},
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


def show_node(*, node_id: int, type_code: str, db_session: Optional[Session] = None) -> Dict[str, Any]:
    with _transaction(db_session) as session:
        node = _load_node_ref(session, node_id=int(node_id), expected_type_code=type_code)
        return {'id': node['id'], 'type_code': node['type_code'], 'title': node['name'], 'attributes': node['attributes']}


def show_quest(*, quest_id: int, db_session: Optional[Session] = None) -> Dict[str, Any]:
    with _transaction(db_session) as session:
        quest = _load_node_ref(session, node_id=int(quest_id), expected_type_code='quest')
        attrs = quest['attributes']
        situation = _load_node_ref(session, node_id=int(attrs.get('situation_id')), expected_type_code='situation')
        goal = _load_node_ref(session, node_id=int(attrs.get('goal_id')), expected_type_code='goal')
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
        completed = 0
        for row in objectives:
            task_attrs = row.attributes if isinstance(row.attributes, dict) else json.loads(row.attributes or '{}')
            state = str(task_attrs.get('current_state') or '')
            if state in _QUEST_TERMINAL_OBJECTIVE_STATES:
                completed += 1
            objective_items.append(
                {
                    'task_id': int(row.id),
                    'title': row.name,
                    'current_state': state,
                    'objective_kind': task_attrs.get('objective_kind'),
                    'required_capabilities': task_attrs.get('required_capabilities') or [],
                }
            )
        total = len(objective_items)
        progress = {
            'total_objectives': total,
            'completed_objectives': completed,
            'percent': int(round((completed / total) * 100)) if total else 0,
        }
        return {
            'quest': {'id': quest['id'], 'title': quest['name'], 'attributes': attrs},
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
    'create_situation',
    'create_goal',
    'create_quest',
    'list_nodes',
    'show_node',
    'show_quest',
    'validate_situation_semantics',
]
