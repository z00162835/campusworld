from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.task import quest_interaction_projection
from app.services.task.quest_interaction_projection import _recommended_objective_id


def _objective(
    objective_id: str,
    *,
    state: str = 'open',
    priority: str = 'normal',
    due_at: str | None = None,
    blocked: bool = False,
    scoped_at_ref: str | None = None,
):
    return {
        'id': objective_id,
        'state': state,
        'priority': priority,
        'dueAt': due_at,
        'blocked': blocked,
        'scopedAtRef': scoped_at_ref,
    }


def test_recommendation_excludes_blocked_and_non_actionable_objectives():
    objectives = [
        _objective('blocked', priority='urgent', blocked=True),
        _objective('review', state='pending_review', priority='urgent'),
        _objective('ready', state='open'),
    ]

    assert _recommended_objective_id(objectives, current_location_id=7) == 'ready'


def test_recommendation_prefers_actionable_state_then_priority_deadline_and_location():
    objectives = [
        _objective('later', state='open', priority='urgent', due_at='2026-12-01T00:00:00Z', scoped_at_ref='7'),
        _objective('working', state='in_progress', priority='normal'),
        _objective('urgent', state='open', priority='urgent', due_at='2026-11-01T00:00:00Z'),
    ]

    assert _recommended_objective_id(objectives, current_location_id=7) == 'working'

    objectives[1]['blocked'] = True
    assert _recommended_objective_id(objectives, current_location_id=7) == 'urgent'


def test_projection_passes_authoritative_location_to_quest_summary(monkeypatch):
    monkeypatch.setattr(quest_interaction_projection, 'read_projection_cursor', lambda *_args, **_kwargs: ('3', '9'))
    monkeypatch.setattr(
        quest_interaction_projection,
        '_visible_tracked_quest_ids',
        lambda *_args, **_kwargs: [11],
    )
    monkeypatch.setattr(
        quest_interaction_projection,
        '_focused_objective',
        lambda *_args, **_kwargs: (None, None),
    )
    monkeypatch.setattr(quest_interaction_projection, 'show_quest', lambda **_kwargs: {'quest': {'id': 11}})
    monkeypatch.setattr(
        quest_interaction_projection,
        '_quest_summary',
        lambda _session, _data, **kwargs: {
            'id': '11',
            'received_location': kwargs['current_location_id'],
        },
    )
    monkeypatch.setattr(
        quest_interaction_projection,
        '_build_journal',
        lambda *_args, **_kwargs: {'nodes': [], 'edges': [], 'unresolvedRefs': []},
    )
    monkeypatch.setattr(quest_interaction_projection, '_world_pulse', lambda *_args, **_kwargs: [])
    monkeypatch.setattr(quest_interaction_projection, '_world_feedback', lambda *_args, **_kwargs: [])

    projection = quest_interaction_projection.build_quest_interaction_projection(
        object(),
        account_node_id=1,
        current_location_id=7,
        actor=object(),
    )

    assert projection['trackedQuests'][0]['received_location'] == 7


def test_quest_summary_recommends_visible_objective_near_current_location(monkeypatch):
    class EmptyRows:
        def first(self):
            return None

        def all(self):
            return []

    class EmptySession:
        def execute(self, *_args, **_kwargs):
            return EmptyRows()

    monkeypatch.setattr(quest_interaction_projection, 'can_read_semantic_node', lambda *_args, **_kwargs: True)
    data = {
        'quest': {'id': 11, 'title': 'Quest', 'attributes': {}},
        'situation': {'id': 31, 'assertion': 'Issue', 'attributes': {}},
        'goal': {'id': 41, 'attributes': {}},
        'objectives': [
            {
                'task_id': 21, 'title': 'Remote Objective', 'current_state': 'open',
                'priority': 'normal', 'due_at': None, 'blocked': False, 'scoped_at_id': 8,
            },
            {
                'task_id': 22, 'title': 'Nearby Objective', 'current_state': 'open',
                'priority': 'normal', 'due_at': None, 'blocked': False, 'scoped_at_id': 7,
            },
        ],
        'progress': {'percent': 0},
    }

    summary = quest_interaction_projection._quest_summary(
        EmptySession(),
        data,
        account_node_id=1,
        current_location_id=7,
        actor=object(),
        focused_objective_id=None,
    )

    assert summary['recommendedObjectiveId'] == '22'
    assert summary['objectives'] == [
        {'id': '21', 'title': 'Remote Objective', 'state': 'open'},
        {'id': '22', 'title': 'Nearby Objective', 'state': 'open'},
    ]


def test_world_pulse_projects_only_readable_situations_and_attention(monkeypatch):
    class Result:
        def __init__(self, rows):
            self.rows = rows

        def fetchall(self):
            return self.rows

    class Session:
        def execute(self, query, _params):
            if 'FROM situation_attention' in query.text:
                return Result([SimpleNamespace(
                    situation_node_id=7, seen_at=None,
                    snoozed_until=None, ui_dismissed_at=datetime.now(timezone.utc),
                )])
            return Result([
                SimpleNamespace(id=7, title='Hidden', attributes={'severity': 'critical', 'assertion': 'Hidden issue'}),
                SimpleNamespace(id=8, title='Visible', attributes={'severity': 'high', 'assertion': 'Visible issue'}),
            ])

    monkeypatch.setattr(quest_interaction_projection, 'can_read_semantic_node', lambda _session, *, node_id, actor: node_id == 8)
    pulse = quest_interaction_projection._world_pulse(Session(), account_node_id=1, actor=object())

    assert pulse == [{
        'id': '8', 'situationId': '8', 'severity': 'high', 'assertion': 'Visible issue',
        'attention': 'new', 'snoozedUntil': None,
    }]


def test_world_feedback_uses_visible_objective_transitions(monkeypatch):
    class Result:
        def __init__(self, rows):
            self.rows = rows

        def fetchall(self):
            return self.rows

    class Session:
        def execute(self, query, *_args, **_kwargs):
            if 'SELECT id FROM nodes' in query.text:
                return Result([SimpleNamespace(id=21), SimpleNamespace(id=22)])
            assert _args[0]['visible_task_ids'] == [21]
            return Result([SimpleNamespace(
                task_node_id=21, to_state='failed', event='complete',
                actor_principal_id=5, actor_principal_kind='user', correlation_id='corr-1',
                created_at=datetime(2026, 10, 1, tzinfo=timezone.utc), quest_id='11',
                objective_title='Inspect bearing',
            )])

    def visible_ids(_session, _actor, candidates):
        assert candidates == [21, 22]
        return [21]

    monkeypatch.setattr(quest_interaction_projection, 'visible_task_ids', visible_ids)
    feedback = quest_interaction_projection._world_feedback(
        Session(), tracked_quest_ids=[11], actor=object(),
    )

    assert feedback[0]['actorKind'] == 'human'
    assert feedback[0]['status'] == 'failed'
    assert feedback[0]['questId'] == '11'
