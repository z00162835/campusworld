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


def test_companion_projection_carries_immutable_collaboration_identity(monkeypatch):
    monkeypatch.setattr(quest_interaction_projection, 'can_read_semantic_node', lambda *_args, **_kwargs: True)
    class Session:
        def execute(self, query, _params):
            rows = [SimpleNamespace(collaboration_relationship_id=91, target_id=99, name='Guide',
                attributes={'role': 'advisor'})] if "'ASSISTED_BY'" in str(query) else []
            return SimpleNamespace(all=lambda: rows, first=lambda: None)
    summary = quest_interaction_projection._quest_summary(Session(), {
        'quest': {'id': 11, 'title': 'Quest', 'attributes': {}}, 'objectives': [],
    }, account_node_id=1, current_location_id=None, actor=object(), focused_objective_id=None)
    assert summary['companion']['collaborationRelationshipId'] == '91'
    assert summary['companion']['id'] == '99'


def test_world_pulse_projects_only_readable_situations_and_attention(monkeypatch):
    class Result:
        def __init__(self, rows):
            self.rows = rows

        def fetchall(self):
            return self.rows

    class Session:
        def execute(self, query, _params):
            if 'SELECT task.id FROM nodes' in query.text:
                return Result([])
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
            if 'FROM task_events' in query.text:
                return Result([])
            return Result([SimpleNamespace(
                transition_id=101, task_node_id=21, to_state='failed', event='complete',
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


def test_new_execution_escalation_resurfaces_an_older_ui_dismissal(monkeypatch):
    old = datetime(2026, 10, 1, tzinfo=timezone.utc)
    recent = datetime(2026, 11, 14, tzinfo=timezone.utc)
    escalation = SimpleNamespace(id=99, created_at=recent, task_node_id=21,
        correlation_id='corr-99', payload={'reasonCode': 'low_confidence'})
    monkeypatch.setattr(quest_interaction_projection, '_latest_execution_escalations', lambda *_args, **_kwargs: {7: escalation})
    monkeypatch.setattr(quest_interaction_projection, 'can_read_semantic_node', lambda *_args, **_kwargs: True)
    class Session:
        def execute(self, query, _params):
            rows = ([SimpleNamespace(situation_node_id=7, updated_at=old, ui_dismissed_at=old,
                                    snoozed_until=None, seen_at=None)] if 'situation_attention' in query.text
                    else [SimpleNamespace(id=7, title='Anomaly', attributes={'severity': 'high', 'assertion': 'Vibration'})])
            return SimpleNamespace(fetchall=lambda: rows)
    pulse = quest_interaction_projection._world_pulse(Session(), account_node_id=1, actor=object())
    assert pulse[0]['attention'] == 'new'
    assert pulse[0]['escalation'] == {'reasonCode': 'low_confidence', 'objectiveId': '21', 'correlationId': 'corr-99'}


def test_latest_execution_filter_cannot_reveal_unreadable_objective_failures(monkeypatch):
    calls = []
    class Session:
        def execute(self, query, params):
            calls.append(query.text)
            return SimpleNamespace(fetchall=lambda: [SimpleNamespace(id=21)])
    monkeypatch.setattr(quest_interaction_projection, 'visible_task_ids', lambda *_args: set())
    assert quest_interaction_projection._latest_execution_escalations(Session(), situation_ids=[7], actor=object()) == {}
    assert len(calls) == 1
    assert 'task_events' not in calls[0]


def test_latest_success_removes_execution_escalation_without_resolving_situation(monkeypatch):
    class Session:
        def execute(self, query, params):
            if 'SELECT task.id' in query.text:
                rows = [SimpleNamespace(id=21)]
            else:
                assert 'DISTINCT ON (event.task_node_id)' in query.text
                assert params['visible_task_ids'] == [21]
                rows = [SimpleNamespace(kind='quest.action.succeeded', situation_id='7')]
            return SimpleNamespace(fetchall=lambda: rows)
    monkeypatch.setattr(quest_interaction_projection, 'visible_task_ids', lambda *_args: {21})
    assert quest_interaction_projection._latest_execution_escalations(Session(), situation_ids=[7], actor=object()) == {}


def test_feedback_merges_action_audit_and_same_timestamp_transitions_with_unique_ids(monkeypatch):
    at = datetime(2026, 11, 14, tzinfo=timezone.utc)
    shared = dict(task_node_id=21, actor_principal_id=99, actor_principal_kind='agent',
                  correlation_id='corr-run', created_at=at, quest_id='11', objective_title='Inspect')
    class Session:
        def execute(self, query, params):
            if 'SELECT id FROM nodes' in query.text:
                rows = [SimpleNamespace(id=21)]
            elif 'FROM task_events' in query.text:
                assert params['visible_task_ids'] == [21]
                rows = [SimpleNamespace(id=201, kind='quest.action.escalated', payload={'reasonCode': 'missing_evidence'}, **shared)]
            else:
                rows = [SimpleNamespace(transition_id=i, to_state='in_progress', event='start', **shared) for i in [101, 102]]
            return SimpleNamespace(fetchall=lambda: rows)
    monkeypatch.setattr(quest_interaction_projection, 'visible_task_ids', lambda *_args: {21})
    feedback = quest_interaction_projection._world_feedback(Session(), tracked_quest_ids=[11], actor=object())
    assert len({item['id'] for item in feedback}) == 3
    action = next(item for item in feedback if item['id'] == 'quest-action:201')
    assert action['status'] == 'escalated'
    assert action['actorKind'] == 'agent'
    assert action['reasonCode'] == 'missing_evidence'
    assert 'objectiveState' not in action
