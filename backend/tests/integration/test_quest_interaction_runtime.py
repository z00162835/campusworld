"""PostgreSQL contracts for durable Quest interaction state."""
from __future__ import annotations

import os
import uuid
from typing import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services.task.errors import IdempotencyConflictError, OptimisticLockError
from app.services.task.permissions import Principal, TASK_READ, TASK_UPDATE
from app.services.task.quest_interaction_projection import build_quest_interaction_projection
from app.services.task.quest_interaction_service import (
    focus_objective,
    set_clue_pin,
    set_collaborator,
    track_quest,
    untrack_quest,
)
from app.services.task.quest_semantic_service import (
    create_goal,
    create_observation,
    create_quest,
    create_situation,
    show_quest,
)
from app.services.task.task_state_machine import create_task

_DB_URL = os.environ.get('CAMPUSWORLD_TEST_DATABASE_URL', '').strip()
pytestmark = pytest.mark.postgres_integration


@pytest.fixture(scope='module')
def engine():
    if not _DB_URL or not _DB_URL.lower().startswith('postgresql'):
        pytest.skip('CAMPUSWORLD_TEST_DATABASE_URL not set; skipping Quest interaction tests.')
    eng = create_engine(_DB_URL, future=True)
    from db.schema_migrations import (
        ensure_graph_seed_ontology,
        ensure_quest_interaction_runtime_schema,
        ensure_task_system_schema,
        ensure_task_system_seed,
    )

    ensure_graph_seed_ontology(eng)
    ensure_task_system_schema(eng)
    ensure_quest_interaction_runtime_schema(eng)
    ensure_task_system_seed(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine) -> Generator:
    Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    value = Session()
    try:
        yield value
    finally:
        value.rollback()
        value.close()


def _account(session) -> int:
    row = session.execute(
        text(
            """
            INSERT INTO nodes (type_id, type_code, name, attributes, is_active, is_public)
            SELECT id, 'account', :name, '{}'::jsonb, TRUE, FALSE
              FROM node_types
             WHERE type_code = 'default_object'
            RETURNING id
            """
        ),
        {'name': f'quest-account-{uuid.uuid4()}'},
    ).first()
    session.commit()
    return int(row.id)


def _quest(session, actor: Principal, suffix: str):
    situation = create_situation(
        title=f'Situation {suffix}',
        assertion=f'Assertion {suffix}',
        actor=actor,
        db_session=session,
    )
    goal = create_goal(
        title=f'Goal {suffix}',
        situation_id=situation.node_id,
        desired_state=f'Desired {suffix}',
        actor=actor,
        db_session=session,
    )
    quest = create_quest(
        title=f'Quest {suffix}',
        situation_id=situation.node_id,
        goal_id=goal.node_id,
        actor=actor,
        db_session=session,
    )
    objective = create_task(
        title=f'Objective {suffix}',
        actor=actor,
        quest_id=quest.node_id,
        db_session=session,
    )
    return quest, objective


def test_multi_track_focus_pin_revision_and_selective_untrack(session):
    account_id = _account(session)
    actor = Principal(
        id=account_id,
        kind='user',
        permissions=frozenset({TASK_READ, TASK_UPDATE}),
    )
    quest_a, objective_a = _quest(session, actor, 'A')
    quest_b, _objective_b = _quest(session, actor, 'B')
    observation = create_observation(
        title='Observed clue',
        assertion='A sourced observation.',
        source_ref='sensor:test',
        provenance={'source_kind': 'sensor', 'capture_method': 'integration_test'},
        observed_at='2026-10-11T10:00:00+08:00',
        subject_id=int(quest_a.attributes['situation_id']),
        actor=actor,
        db_session=session,
    )

    first = track_quest(
        account_node_id=account_id,
        quest_id=quest_a.node_id,
        actor=actor,
        expected_revision='0',
        idempotency_key='track-a',
        db_session=session,
    )
    assert first.projection_revision == '1'
    replay = track_quest(
        account_node_id=account_id,
        quest_id=quest_a.node_id,
        actor=actor,
        expected_revision='0',
        idempotency_key='track-a',
        db_session=session,
    )
    assert replay.idempotent_replay is True
    assert replay.projection_revision == '1'
    with pytest.raises(IdempotencyConflictError, match='different Quest interaction request'):
        untrack_quest(
            account_node_id=account_id,
            quest_id=quest_a.node_id,
            actor=actor,
            expected_revision='1',
            idempotency_key='track-a',
            db_session=session,
        )

    noop = track_quest(
        account_node_id=account_id,
        quest_id=quest_a.node_id,
        actor=actor,
        expected_revision='1',
        idempotency_key='track-a-noop',
        db_session=session,
    )
    assert noop.changed is False
    assert noop.projection_revision == '1'

    second = track_quest(
        account_node_id=account_id,
        quest_id=quest_b.node_id,
        actor=actor,
        expected_revision='1',
        idempotency_key='track-b',
        db_session=session,
    )
    focused = focus_objective(
        account_node_id=account_id,
        quest_id=quest_a.node_id,
        objective_id=objective_a.task_id,
        actor=actor,
        expected_revision=second.projection_revision,
        idempotency_key='focus-a',
        db_session=session,
    )
    discovered_projection = build_quest_interaction_projection(
        session,
        account_node_id=account_id,
        actor=actor,
    )
    discovered_quest = next(
        item for item in discovered_projection['trackedQuests'] if item['id'] == str(quest_a.node_id)
    )
    assert any(
        clue['id'] == str(observation.node_id) and clue['pinned'] is False
        for clue in discovered_quest['clues']
    )
    pinned = set_clue_pin(
        account_node_id=account_id,
        quest_id=quest_a.node_id,
        clue_node_id=observation.node_id,
        pinned=True,
        actor=actor,
        expected_revision=focused.projection_revision,
        idempotency_key='pin-a',
        db_session=session,
    )
    pinned_to_b = set_clue_pin(
        account_node_id=account_id,
        quest_id=quest_b.node_id,
        clue_node_id=observation.node_id,
        pinned=True,
        actor=actor,
        expected_revision=pinned.projection_revision,
        idempotency_key='pin-b',
        db_session=session,
    )
    unpinned_from_b = set_clue_pin(
        account_node_id=account_id,
        quest_id=quest_b.node_id,
        clue_node_id=observation.node_id,
        pinned=False,
        actor=actor,
        expected_revision=pinned_to_b.projection_revision,
        idempotency_key='unpin-b',
        db_session=session,
    )
    session.commit()

    projection = build_quest_interaction_projection(
        session,
        account_node_id=account_id,
        actor=actor,
    )
    assert projection['projectionRevision'] == unpinned_from_b.projection_revision
    assert {item['id'] for item in projection['trackedQuests']} == {
        str(quest_a.node_id),
        str(quest_b.node_id),
    }
    assert projection['foregroundQuestId'] == str(quest_a.node_id)
    quest_a_projection = next(item for item in projection['trackedQuests'] if item['id'] == str(quest_a.node_id))
    assert any(clue['id'] == str(observation.node_id) and clue['pinned'] for clue in quest_a_projection['clues'])
    assert any(node['id'] == str(observation.node_id) for node in projection['questJournal']['nodes'])
    assert pinned_to_b.changed is True
    assert unpinned_from_b.changed is True

    with pytest.raises(OptimisticLockError, match='stale_projection'):
        untrack_quest(
            account_node_id=account_id,
            quest_id=quest_a.node_id,
            actor=actor,
            expected_revision='1',
            idempotency_key='stale-untrack',
            db_session=session,
        )

    removed = untrack_quest(
        account_node_id=account_id,
        quest_id=quest_a.node_id,
        actor=actor,
        expected_revision=pinned.projection_revision,
        idempotency_key='untrack-a',
        db_session=session,
    )
    session.commit()
    after = build_quest_interaction_projection(session, account_node_id=account_id, actor=actor)
    assert removed.projection_revision == after['projectionRevision']
    assert [item['id'] for item in after['trackedQuests']] == [str(quest_b.node_id)]
    assert after['foregroundQuestId'] == str(quest_b.node_id)


def test_collaboration_records_validity_window(session):
    account_id = _account(session)
    actor = Principal(id=account_id, kind='user', permissions=frozenset({TASK_READ, TASK_UPDATE}))
    quest, _objective = _quest(session, actor, 'collaboration')
    agent = session.execute(
        text(
            """
            INSERT INTO nodes (type_id, type_code, name, attributes, is_active, is_public)
            SELECT id, 'npc_agent', :name, '{}'::jsonb, TRUE, TRUE
              FROM node_types
             WHERE type_code = 'default_object'
            RETURNING id
            """
        ),
        {'name': f'quest-agent-{uuid.uuid4()}'},
    ).first()
    advisor = session.execute(
        text(
            """
            INSERT INTO nodes (type_id, type_code, name, attributes, is_active, is_public)
            SELECT id, 'npc_agent', :name, '{}'::jsonb, TRUE, TRUE
              FROM node_types
             WHERE type_code = 'default_object'
            RETURNING id
            """
        ),
        {'name': f'quest-advisor-{uuid.uuid4()}'},
    ).first()
    session.commit()

    tracked = track_quest(
        account_node_id=account_id,
        quest_id=quest.node_id,
        actor=actor,
        expected_revision='0',
        idempotency_key='collaboration-track',
        db_session=session,
    )
    added = set_collaborator(
        account_node_id=account_id,
        quest_id=quest.node_id,
        agent_node_id=int(agent.id),
        active=True,
        actor=actor,
        expected_revision=tracked.projection_revision,
        idempotency_key='collaborator-add',
        is_primary_companion=True,
        db_session=session,
    )
    active_projection = build_quest_interaction_projection(
        session,
        account_node_id=account_id,
        actor=actor,
    )
    assert active_projection['trackedQuests'][0]['companion'] == {
        'id': str(agent.id),
        'name': str(agent.name),
        'role': 'advisor',
        'isPrimary': True,
    }
    added_advisor = set_collaborator(
        account_node_id=account_id,
        quest_id=quest.node_id,
        agent_node_id=int(advisor.id),
        active=True,
        actor=actor,
        expected_revision=added.projection_revision,
        idempotency_key='advisor-add',
        is_primary_companion=False,
        db_session=session,
    )
    removed = set_collaborator(
        account_node_id=account_id,
        quest_id=quest.node_id,
        agent_node_id=int(agent.id),
        active=False,
        actor=actor,
        expected_revision=added_advisor.projection_revision,
        idempotency_key='collaborator-remove',
        db_session=session,
    )
    row = session.execute(
        text("SELECT attributes FROM relationships WHERE id = :id"),
        {'id': added.relationship_id},
    ).first()
    assert removed.changed is True
    assert row.attributes['valid_from']
    assert row.attributes['valid_to']
    assert row.attributes['status'] == 'ended'

    # Ended collaborators are not resolved as the current Companion.
    projection = build_quest_interaction_projection(
        session,
        account_node_id=account_id,
        actor=actor,
    )
    assert projection['trackedQuests'][0]['companion'] is None
    assert projection['trackedQuests'][0]['companionFallback'] == 'aico'


def test_public_quest_filters_objectives_by_task_acl(session):
    owner_id = _account(session)
    reader_id = _account(session)
    owner = Principal(id=owner_id, kind='user', permissions=frozenset({TASK_READ, TASK_UPDATE}))
    reader = Principal(id=reader_id, kind='user', permissions=frozenset({TASK_READ}))
    quest, objective = _quest(session, owner, 'acl-filter')
    session.execute(
        text(
            """
            UPDATE nodes
               SET is_public = TRUE
             WHERE id = ANY(:ids)
            """
        ),
        {
            'ids': [
                quest.node_id,
                int(quest.attributes['situation_id']),
                int(quest.attributes['goal_id']),
            ],
        },
    )
    session.commit()

    view = show_quest(quest_id=quest.node_id, actor=reader, db_session=session)

    assert view['quest']['id'] == quest.node_id
    assert all(item['task_id'] != objective.task_id for item in view['objectives'])
