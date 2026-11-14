"""Authorized, bounded Quest interaction read projection."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.task.permissions import Principal
from app.services.task.task_visibility_sql import visible_task_ids
from app.services.task.quest_interaction_service import read_projection_cursor
from app.services.task.quest_semantic_service import (
    can_read_semantic_node,
    resolve_semantic_node_ref,
    show_quest,
)

CONTRACT_VERSION = 'quest-interaction.v1'
CAPABILITIES = [
    'multi_quest_tracking',
    'durable_focus',
    'observation_clues',
    'quest_graph',
    'situation_attention',
    'world_feedback',
]
_EDGE_TYPES = frozenset(
    {
        'TRACKS_QUEST',
        'FOCUSES_ON',
        'PINS_CLUE',
        'RESPONDS_TO',
        'PURSUES',
        'HAS_OBJECTIVE',
        'BASED_ON_FACT',
        'SUPPORTED_BY',
        'SCOPED_AT',
        'ASSISTED_BY',
    }
)
def _attributes(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    try:
        loaded = json.loads(value or '{}')
    except (TypeError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _recommended_objective_id(
    objectives: List[Dict[str, Any]],
    *,
    current_location_id: Optional[int],
) -> Optional[str]:
    actionable_order = {'in_progress': 0, 'claimed': 1, 'open': 2, 'rejected': 3}
    priority_order = {'urgent': 0, 'high': 1, 'normal': 2, 'low': 3}
    candidates = [
        (index, item)
        for index, item in enumerate(objectives)
        if item['state'] in actionable_order and not item['blocked']
    ]
    if not candidates:
        return None
    _index, selected = min(
        candidates,
        key=lambda pair: (
            actionable_order[pair[1]['state']],
            priority_order.get(pair[1]['priority'], 2),
            pair[1]['dueAt'] or '9999',
            0 if current_location_id is not None and pair[1]['scopedAtRef'] == str(current_location_id) else 1,
            pair[0],
        ),
    )
    return str(selected['id'])


def _visible_tracked_quest_ids(
    session: Session,
    *,
    account_node_id: int,
    actor: Principal,
    limit: int,
) -> List[int]:
    rows = session.execute(
        text(
            """
            SELECT r.target_id
              FROM relationships r
              JOIN nodes q ON q.id = r.target_id
             WHERE r.source_id = :account_id
               AND r.type_code = 'TRACKS_QUEST'
               AND r.is_active = TRUE
               AND q.type_code = 'quest'
               AND q.is_active = TRUE
             ORDER BY r.created_at DESC, r.id DESC
             LIMIT :limit
            """
        ),
        {'account_id': int(account_node_id), 'limit': int(limit)},
    ).all()
    return [
        int(row.target_id)
        for row in rows
        if can_read_semantic_node(session, node_id=int(row.target_id), actor=actor)
    ]


def _focused_objective(session: Session, *, account_node_id: int) -> tuple[Optional[int], Optional[int]]:
    row = session.execute(
        text(
            """
            SELECT focus.target_id AS objective_id, member.source_id AS quest_id
              FROM relationships focus
              JOIN relationships member
                ON member.target_id = focus.target_id
               AND member.type_code = 'HAS_OBJECTIVE'
               AND member.is_active = TRUE
              JOIN relationships tracked
                ON tracked.source_id = focus.source_id
               AND tracked.target_id = member.source_id
               AND tracked.type_code = 'TRACKS_QUEST'
               AND tracked.is_active = TRUE
             WHERE focus.source_id = :account_id
               AND focus.type_code = 'FOCUSES_ON'
               AND focus.is_active = TRUE
             ORDER BY focus.created_at DESC, focus.id DESC
             LIMIT 1
            """
        ),
        {'account_id': int(account_node_id)},
    ).first()
    if row is None:
        return None, None
    return int(row.objective_id), int(row.quest_id)


def _quest_summary(
    session: Session,
    data: Dict[str, Any],
    *,
    account_node_id: int,
    current_location_id: Optional[int],
    actor: Principal,
    focused_objective_id: Optional[int],
) -> Dict[str, Any]:
    quest = data['quest']
    quest_attrs = quest.get('attributes') or {}
    situation = data.get('situation') or {}
    goal = data.get('goal') or {}
    goal_attrs = goal.get('attributes') or {}
    objectives = []
    for item in data.get('objectives') or []:
        scoped_at_id = item.get('scoped_at_id')
        objectives.append({
            'id': str(item['task_id']),
            'title': str(item.get('title') or f"Objective {item['task_id']}"),
            'state': str(item.get('current_state') or 'unknown'),
            'priority': str(item.get('priority') or 'normal'),
            'dueAt': item.get('due_at'),
            'blocked': bool(item.get('blocked')),
            'scopedAtRef': (
                str(scoped_at_id)
                if scoped_at_id is not None
                and can_read_semantic_node(session, node_id=int(scoped_at_id), actor=actor)
                else None
            ),
        })
    recommended = _recommended_objective_id(
        objectives,
        current_location_id=current_location_id,
    )
    objective_summaries = [
        {'id': item['id'], 'title': item['title'], 'state': item['state']}
        for item in objectives
    ]
    situation_attrs = situation.get('attributes') or {}
    subject_ref = situation.get('subject_ref')
    if subject_ref is None:
        subject_ref = situation_attrs.get('subject_ref')
    scoped_at_ref = None
    scope_source_ids = [int(value) for value in (situation.get('id'), quest.get('id')) if value is not None]
    if scope_source_ids:
        scope_row = session.execute(
            text(
                """
                SELECT target_id
                  FROM relationships
                 WHERE source_id = ANY(:source_ids)
                   AND type_code = 'SCOPED_AT'
                   AND is_active = TRUE
                 ORDER BY CASE WHEN source_id = :situation_id THEN 0 ELSE 1 END, id
                 LIMIT 1
                """
            ),
            {
                'source_ids': scope_source_ids,
                'situation_id': int(situation['id']) if situation.get('id') is not None else -1,
            },
        ).first()
        if scope_row is not None and can_read_semantic_node(session, node_id=int(scope_row.target_id), actor=actor):
            scoped_at_ref = str(scope_row.target_id)
    related_refs: Set[str] = set()
    if situation.get('id') is not None:
        about_rows = session.execute(
            text(
                """
                SELECT target_id
                  FROM relationships
                 WHERE source_id = :situation_id
                   AND type_code = 'ABOUT'
                   AND is_active = TRUE
                 ORDER BY id
                """
            ),
            {'situation_id': int(situation['id'])},
        ).all()
        for row in about_rows:
            target_id = int(row.target_id)
            if target_id != int(subject_ref or 0) and can_read_semantic_node(session, node_id=target_id, actor=actor):
                related_refs.add(str(target_id))
    for value in situation_attrs.get('related_entity_refs') or []:
        try:
            related_id = int(value)
        except (TypeError, ValueError):
            continue
        if can_read_semantic_node(session, node_id=related_id, actor=actor):
            related_refs.add(str(related_id))
    if subject_ref is not None:
        try:
            subject_id = int(subject_ref)
        except (TypeError, ValueError):
            subject_id = None
        if subject_id is not None and not can_read_semantic_node(session, node_id=subject_id, actor=actor):
            subject_ref = None
    companion = None
    collaborator_rows = session.execute(
        text(
            """
            SELECT r.target_id, r.attributes, n.name, n.type_code
              FROM relationships r
              JOIN nodes n ON n.id = r.target_id
             WHERE r.source_id = :quest_id
               AND r.type_code = 'ASSISTED_BY'
               AND r.is_active = TRUE
               AND COALESCE(r.attributes->>'status', 'active') = 'active'
               AND COALESCE((r.attributes->>'is_primary_companion')::boolean, FALSE) = TRUE
               AND n.is_active = TRUE
             ORDER BY r.created_at, r.id
            """
        ),
        {'quest_id': int(quest['id'])},
    ).all()
    for collaborator in collaborator_rows:
        collaborator_id = int(collaborator.target_id)
        if not can_read_semantic_node(session, node_id=collaborator_id, actor=actor):
            continue
        collaborator_attrs = _attributes(collaborator.attributes)
        companion = {
            'id': str(collaborator_id),
            'name': str(collaborator_attrs.get('display_name') or collaborator.name or 'Companion Agent'),
            'role': str(collaborator_attrs.get('role') or 'companion'),
            'isPrimary': True,
        }
        break
    clue_context_ids = set(related_refs)
    if situation.get('id') is not None:
        clue_context_ids.add(str(situation['id']))
    if subject_ref is not None:
        clue_context_ids.add(str(subject_ref))
    if scoped_at_ref is not None:
        clue_context_ids.add(scoped_at_ref)
    pinned_rows = session.execute(
        text(
            """
            SELECT target_id
              FROM relationships
             WHERE source_id = :account_id
               AND type_code = 'PINS_CLUE'
               AND is_active = TRUE
               AND attributes->>'quest_id' = :quest_id
             ORDER BY created_at DESC, id DESC
             LIMIT 50
            """
        ),
        {'account_id': int(account_node_id), 'quest_id': str(int(quest['id']))},
    ).all()
    pinned_ids = {int(row.target_id) for row in pinned_rows}
    clue_ids = set(pinned_ids)
    if clue_context_ids:
        discovered_rows = session.execute(
            text(
                """
                SELECT DISTINCT observation.id
                  FROM nodes observation
                  LEFT JOIN relationships about
                    ON about.source_id = observation.id
                   AND about.type_code = 'ABOUT'
                   AND about.is_active = TRUE
                 WHERE observation.type_code = 'observation'
                   AND observation.is_active = TRUE
                   AND (
                        about.target_id = ANY(:context_ids)
                     OR EXISTS (
                            SELECT 1
                              FROM relationships evidence_link
                             WHERE evidence_link.source_id = :situation_id
                               AND evidence_link.target_id = observation.id
                               AND evidence_link.type_code = 'BASED_ON_FACT'
                               AND evidence_link.is_active = TRUE
                        )
                   )
                 ORDER BY observation.id DESC
                 LIMIT 50
                """
            ),
            {
                'context_ids': [int(value) for value in clue_context_ids],
                'situation_id': int(situation['id']) if situation.get('id') is not None else -1,
            },
        ).all()
        clue_ids.update(int(row.id) for row in discovered_rows)
    clues = []
    for clue_id in sorted(clue_ids, reverse=True)[:50]:
        if not can_read_semantic_node(session, node_id=clue_id, actor=actor):
            continue
        clue_row = _node_row(session, clue_id)
        if clue_row is None or str(clue_row.type_code) != 'observation':
            continue
        clue_attrs = _attributes(clue_row.attributes)
        clues.append({
            'id': str(clue_id),
            'title': str(clue_attrs.get('title') or clue_row.name or 'Observation'),
            'assertion': str(clue_attrs.get('assertion') or ''),
            'verificationStatus': str(clue_attrs.get('verification_status') or 'unverified'),
            'sourceRef': clue_attrs.get('source_ref'),
            'observedAt': clue_attrs.get('observed_at'),
            'pinned': clue_id in pinned_ids,
        })
    return {
        'id': str(quest['id']),
        'title': str(quest.get('title') or f"Quest {quest['id']}"),
        'state': str(quest_attrs.get('current_state') or 'draft'),
        'riskLevel': str(quest_attrs.get('risk_level') or 'normal'),
        'tracking': 'explicit',
        'focusedObjectiveId': str(focused_objective_id) if focused_objective_id is not None else None,
        'recommendedObjectiveId': recommended,
        'situation': {
            'id': str(situation['id']),
            'assertion': str(situation.get('assertion') or ''),
            'triggerKind': str(situation_attrs.get('trigger_kind') or 'manual'),
            'confidence': situation_attrs.get('confidence'),
            'severity': str(situation_attrs.get('severity') or 'medium'),
            'primarySubjectRef': str(subject_ref) if subject_ref is not None else None,
            'relatedEntityRefs': sorted(related_refs),
            'scopedAtRef': scoped_at_ref,
        } if situation else None,
        'goal': {
            'id': str(goal['id']),
            'desiredState': str(goal_attrs.get('desired_state') or ''),
        } if goal else None,
        'objectives': objective_summaries,
        'progress': dict(data.get('progress') or {}),
        'companion': companion,
        'companionFallback': None if companion else 'aico',
        'clues': clues,
    }


def _node_row(session: Session, node_id: int) -> Optional[Any]:
    return session.execute(
        text(
            """
            SELECT id, type_code, name, attributes, is_public
              FROM nodes
             WHERE id = :node_id
               AND is_active = TRUE
            """
        ),
        {'node_id': int(node_id)},
    ).first()


def _journal_node(row: Any, *, label: Optional[str] = None) -> Dict[str, Any]:
    attrs = _attributes(row.attributes)
    item = {
        'id': str(row.id),
        'type': str(row.type_code),
        'label': str(label or attrs.get('title') or attrs.get('display_name') or row.name or row.type_code),
    }
    if attrs.get('verification_status') is not None:
        item['verificationStatus'] = str(attrs['verification_status'])
    return item


def _collect_unresolved_refs(
    session: Session,
    *,
    quest_data: Dict[str, Any],
    visible_node_ids: Set[int],
) -> List[Dict[str, str]]:
    quest_attrs = quest_data['quest'].get('attributes') or {}
    situation = quest_data.get('situation') or {}
    pairs: List[tuple[str, str]] = []
    for value in situation.get('fact_refs') or []:
        pairs.append((str(value), 'fact'))
    for value in situation.get('evidence_refs') or []:
        pairs.append((str(value), 'evidence'))
    for field, expected in (
        ('policy_refs', 'policy'),
        ('process_refs', 'process_pattern'),
        ('quality_refs', 'quality_spec'),
        ('case_refs', 'case'),
    ):
        for value in quest_attrs.get(field) or []:
            pairs.append((str(value), expected))
    out: List[Dict[str, str]] = []
    seen: Set[str] = set()
    for semantic_ref, expected_type in pairs:
        if semantic_ref in seen:
            continue
        seen.add(semantic_ref)
        resolved = resolve_semantic_node_ref(session, semantic_ref)
        if resolved is None:
            out.append({'ref': semantic_ref, 'expectedType': expected_type, 'reason': 'not_materialized'})
        elif int(resolved) not in visible_node_ids:
            out.append({'ref': semantic_ref, 'expectedType': expected_type, 'reason': 'not_visible'})
    return out


def _build_journal(
    session: Session,
    *,
    account_node_id: int,
    actor: Principal,
    quest_id: Optional[int],
    quest_data: Optional[Dict[str, Any]],
    max_nodes: int,
    max_edges: int,
) -> Dict[str, Any]:
    if quest_id is None or quest_data is None:
        return {'nodes': [], 'edges': [], 'unresolvedRefs': []}
    allowed_ids: Set[int] = {int(account_node_id), int(quest_id)}
    situation = quest_data.get('situation') or {}
    goal = quest_data.get('goal') or {}
    if situation.get('id') is not None:
        allowed_ids.add(int(situation['id']))
    if goal.get('id') is not None:
        allowed_ids.add(int(goal['id']))
    allowed_ids.update(int(item['task_id']) for item in quest_data.get('objectives') or [])

    relation_rows = session.execute(
        text(
            """
            SELECT r.id, r.type_code, r.source_id, r.target_id, r.attributes
              FROM relationships r
             WHERE r.is_active = TRUE
               AND r.type_code = ANY(:edge_types)
               AND (
                    r.source_id = ANY(:root_ids)
                 OR r.target_id = ANY(:root_ids)
               )
             ORDER BY r.created_at ASC, r.id ASC
             LIMIT :limit
            """
        ),
        {
            'edge_types': list(_EDGE_TYPES),
            'root_ids': list(allowed_ids),
            'limit': int(max_edges * 3),
        },
    ).all()

    candidate_edges: List[Any] = []
    for row in relation_rows:
        attrs = _attributes(row.attributes)
        if row.type_code in {'TRACKS_QUEST', 'FOCUSES_ON'} and int(row.source_id) != int(account_node_id):
            continue
        if row.type_code == 'PINS_CLUE':
            if int(row.source_id) != int(account_node_id) or int(attrs.get('quest_id') or 0) != int(quest_id):
                continue
        if row.type_code == 'ASSISTED_BY' and int(row.source_id) != int(quest_id):
            continue
        if int(row.source_id) not in allowed_ids and int(row.target_id) not in allowed_ids:
            continue
        candidate_edges.append(row)
        allowed_ids.add(int(row.source_id))
        allowed_ids.add(int(row.target_id))

    visible_rows: Dict[int, Any] = {}
    structural_ids = {int(account_node_id), int(quest_id)}
    task_ids = {
        node_id
        for node_id in allowed_ids
        if (row := _node_row(session, node_id)) is not None and str(row.type_code) == 'task'
    }
    readable_task_ids = visible_task_ids(session, actor, list(task_ids))
    for node_id in list(allowed_ids):
        if len(visible_rows) >= max_nodes:
            break
        row = _node_row(session, node_id)
        if row is None:
            continue
        type_code = str(row.type_code)
        visible = node_id in structural_ids or bool(row.is_public)
        if type_code == 'task':
            visible = node_id in readable_task_ids
        elif type_code in {'quest', 'situation', 'goal', 'observation', 'fact', 'evidence', 'npc_agent'}:
            visible = can_read_semantic_node(session, node_id=node_id, actor=actor)
        if visible:
            visible_rows[node_id] = row

    nodes = [
        _journal_node(row, label='You' if node_id == int(account_node_id) else None)
        for node_id, row in visible_rows.items()
    ]
    edges = []
    for row in candidate_edges:
        if len(edges) >= max_edges:
            break
        if int(row.source_id) not in visible_rows or int(row.target_id) not in visible_rows:
            continue
        edges.append(
            {
                'id': str(row.id),
                'type': str(row.type_code),
                'sourceId': str(row.source_id),
                'targetId': str(row.target_id),
            }
        )
    return {
        'nodes': nodes,
        'edges': edges,
        'unresolvedRefs': _collect_unresolved_refs(
            session,
            quest_data=quest_data,
            visible_node_ids=set(visible_rows),
        ),
    }


def _world_pulse(session: Session, *, account_node_id: int, actor: Principal, limit: int = 30) -> List[Dict[str, Any]]:
    rows = session.execute(
        text("""
            SELECT id, title, attributes
              FROM nodes
             WHERE type_code = 'situation'
             ORDER BY updated_at DESC, id DESC
             LIMIT :limit
        """),
        {'limit': max(1, min(int(limit), 100))},
    ).fetchall()
    pulse: List[Dict[str, Any]] = []
    attention_rows = session.execute(
        text("""
            SELECT situation_node_id, seen_at, snoozed_until, ui_dismissed_at
              FROM situation_attention
             WHERE account_node_id = :account_id
        """),
        {'account_id': int(account_node_id)},
    ).fetchall()
    attention_by_id = {int(row.situation_node_id): row for row in attention_rows}
    now = datetime.now(tz=timezone.utc)
    for row in rows:
        situation_id = int(row.id)
        if not can_read_semantic_node(session, node_id=situation_id, actor=actor):
            continue
        attrs = _attributes(row.attributes)
        if str(attrs.get('current_state') or '').lower() in {'resolved', 'closed', 'cancelled'}:
            continue
        attention = attention_by_id.get(situation_id)
        snooze_until = getattr(attention, 'snoozed_until', None) if attention is not None else None
        dismissed_at = getattr(attention, 'ui_dismissed_at', None) if attention is not None else None
        seen_at = getattr(attention, 'seen_at', None) if attention is not None else None
        if dismissed_at is not None:
            attention_state = 'ui_dismissed'
        elif snooze_until is not None and snooze_until > now:
            attention_state = 'snoozed'
        elif seen_at is not None:
            attention_state = 'seen'
        else:
            attention_state = 'new'
        pulse.append({
            'id': str(situation_id),
            'situationId': str(situation_id),
            'severity': str(attrs.get('severity') or 'medium'),
            'assertion': str(attrs.get('assertion') or row.title or ''),
            'attention': attention_state,
            'snoozedUntil': snooze_until.isoformat() if attention_state == 'snoozed' else None,
        })
    pulse.sort(key=lambda item: (
        {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}.get(item['severity'].lower(), 4),
        0 if item['attention'] == 'new' else 1,
        item['id'],
    ))
    return pulse[:max(1, min(int(limit), 100))]


def _world_feedback(
    session: Session,
    *,
    tracked_quest_ids: List[int],
    actor: Principal,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    if not tracked_quest_ids:
        return []
    candidate_rows = session.execute(
        text("""
            SELECT id FROM nodes
             WHERE type_code = 'task'
               AND attributes->>'quest_id' = ANY(:quest_ids)
             LIMIT 500
        """),
        {'quest_ids': [str(int(quest_id)) for quest_id in tracked_quest_ids]},
    ).fetchall()
    candidate_ids = [int(row.id) for row in candidate_rows]
    visible_ids = sorted(visible_task_ids(session, actor, candidate_ids))
    if not visible_ids:
        return []
    rows = session.execute(
        text("""
            SELECT transition.task_node_id, transition.to_state, transition.event,
                   transition.actor_principal_id, transition.actor_principal_kind,
                   transition.correlation_id, transition.created_at,
                   task.attributes->>'quest_id' AS quest_id,
                   task.title AS objective_title
              FROM task_state_transitions AS transition
              JOIN nodes AS task ON task.id = transition.task_node_id
             WHERE transition.task_node_id = ANY(:visible_task_ids)
               AND task.attributes->>'quest_id' = ANY(:quest_ids)
             ORDER BY transition.created_at DESC, transition.id DESC
             LIMIT :limit
        """),
        {
            'visible_task_ids': visible_ids,
            'quest_ids': [str(int(quest_id)) for quest_id in tracked_quest_ids],
            'limit': max(1, min(int(limit), 100)),
        },
    ).fetchall()
    feedback: List[Dict[str, Any]] = []
    for row in rows:
        state = str(row.to_state or '').lower()
        status = 'failed' if state == 'failed' else 'blocked' if state in {'blocked', 'rejected'} else 'succeeded'
        raw_actor_kind = str(row.actor_principal_kind or 'system').lower()
        actor_kind = 'human' if raw_actor_kind in {'human', 'user'} else raw_actor_kind
        if actor_kind not in {'human', 'agent', 'system'}:
            actor_kind = 'system'
        feedback.append({
            'id': f"transition:{row.task_node_id}:{row.created_at.isoformat()}",
            'questId': str(row.quest_id),
            'objectiveId': str(row.task_node_id),
            'actorKind': actor_kind,
            'actorId': str(row.actor_principal_id) if row.actor_principal_id is not None else None,
            'status': status,
            'summary': str(row.objective_title or 'Objective'),
            'objectiveState': state or str(row.event),
            'correlationId': str(row.correlation_id or ''),
            'occurredAt': row.created_at.isoformat(),
        })
    return feedback


def build_quest_interaction_projection(
    session: Session,
    *,
    account_node_id: int,
    current_location_id: Optional[int] = None,
    actor: Principal,
    max_tracked_quests: int = 20,
    max_journal_nodes: int = 80,
    max_journal_edges: int = 120,
) -> Dict[str, Any]:
    """Build a single-version Quest HUD and Journal projection."""
    revision, last_event_id = read_projection_cursor(session, account_node_id=account_node_id)
    quest_ids = _visible_tracked_quest_ids(
        session,
        account_node_id=account_node_id,
        actor=actor,
        limit=max_tracked_quests,
    )
    focused_objective_id, focused_quest_id = _focused_objective(
        session,
        account_node_id=account_node_id,
    )
    if focused_quest_id not in quest_ids:
        focused_objective_id = None
        focused_quest_id = None
    foreground_quest_id = focused_quest_id or (quest_ids[0] if quest_ids else None)

    quest_data_by_id: Dict[int, Dict[str, Any]] = {}
    tracked: List[Dict[str, Any]] = []
    for quest_id in quest_ids:
        data = show_quest(quest_id=quest_id, actor=actor, db_session=session)
        quest_data_by_id[quest_id] = data
        tracked.append(
            _quest_summary(
                session,
                data,
                account_node_id=account_node_id,
                current_location_id=current_location_id,
                actor=actor,
                focused_objective_id=focused_objective_id if quest_id == focused_quest_id else None,
            )
        )

    return {
        'contractVersion': CONTRACT_VERSION,
        'capabilities': list(CAPABILITIES),
        'projectionRevision': revision,
        'lastEventId': last_event_id,
        'trackedQuests': tracked,
        'foregroundQuestId': str(foreground_quest_id) if foreground_quest_id is not None else None,
        'questJournal': _build_journal(
            session,
            account_node_id=account_node_id,
            actor=actor,
            quest_id=foreground_quest_id,
            quest_data=quest_data_by_id.get(foreground_quest_id) if foreground_quest_id is not None else None,
            max_nodes=max_journal_nodes,
            max_edges=max_journal_edges,
        ),
        'worldPulse': _world_pulse(session, account_node_id=account_node_id, actor=actor),
        'worldFeedback': _world_feedback(
            session,
            tracked_quest_ids=quest_ids,
            actor=actor,
        ),
    }


__all__ = [
    'CAPABILITIES',
    'CONTRACT_VERSION',
    'build_quest_interaction_projection',
]
