"""Published graph version/control evaluation, no live graph writes."""
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.task import quest_governance as module
from app.services.task.permissions import Principal
from app.services.task.quest_decision import QuestDecisionContext
from app.services.task.errors import ReferenceNotFound


@pytest.fixture
def graph(monkeypatch):
    fixture = json.loads((Path(__file__).parents[1] / 'fixtures/quest_runtime/readonly_inspection_v1.json').read_text())
    nodes = {
        11: {'id': 11, 'type_code': 'quest', 'attributes': {'current_state': 'executing', 'execution_hold': False,
            'state_version': 1, 'governance_mode': 'enforced', 'situation_id': 31, 'goal_id': 41, 'risk_level': 'normal',
            'policy_refs': [fixture['policy_ref']], 'process_refs': [fixture['process_ref']]}},
        21: {'id': 21, 'type_code': 'task', 'attributes': {'quest_id': 11, 'state_version': 2}},
        31: {'id': 31, 'type_code': 'situation', 'attributes': {'confidence': 0.95}},
        41: {'id': 41, 'type_code': 'goal', 'attributes': {'constraints': {}}},
        51: {'id': 51, 'type_code': 'observation', 'attributes': {'verification_status': 'unverified'}},
    }
    sources = {
        fixture['policy_ref']: SimpleNamespace(id=101, type_code='policy', attributes={
            'version': '1', 'publication_state': 'published', 'definition': fixture['policy_definition']}),
        fixture['process_ref']: SimpleNamespace(id=102, type_code='process_pattern', attributes={
            'version': '1', 'publication_state': 'published', 'definition': fixture['process_definition']}),
    }
    visible = {11, 21, 31, 41, 51, 101, 102}
    def load(_session, *, node_id, expected_type_code=None):
        row = nodes.get(node_id)
        if row is None or (expected_type_code and row['type_code'] != expected_type_code):
            raise ReferenceNotFound('missing')
        return row
    monkeypatch.setattr(module, 'load_node_ref', load)
    monkeypatch.setattr(module, 'can_read_semantic_node', lambda _session, *, node_id, actor: node_id in visible)
    monkeypatch.setattr(module, 'visible_task_ids', lambda _session, _actor, ids: set(ids) & visible)
    session_state = SimpleNamespace(duplicate=False, linked=True)
    class Session:
        def execute(self, query, params):
            rows = [sources[params['ref']]] if params.get('ref') in sources else []
            if session_state.duplicate and rows:
                rows = rows * 2
            return SimpleNamespace(all=lambda: rows, first=lambda: (1,) if session_state.linked else None)
    context = QuestDecisionContext(quest_id=11, objective_id=21,
        actor=Principal(id=99, kind='agent', permissions=frozenset({'task.read'})), agent_node_id=99,
        command_line='look', projection_revision='7', pinned_rule_refs=(fixture['policy_ref'], fixture['process_ref']),
        correlation_id='test-governance', quest_state_version=1, objective_state_version=2)
    return SimpleNamespace(session=Session(), context=context, nodes=nodes, visible=visible, sources=sources,
        state=session_state, policy=fixture['policy_definition'], process=fixture['process_definition'])


def evaluate(graph):
    return module.GraphQuestGovernance()(graph.session, graph.context)


def test_published_exact_policy_and_process_allow_readonly_registered_scenario(graph):
    result = evaluate(graph)
    assert result.decision == 'allow'
    assert result.rule_refs == graph.context.pinned_rule_refs
    assert result.context is graph.context


@pytest.mark.parametrize('state', ['draft', 'accepted', 'closed', 'cancelled'])
def test_non_executing_quest_cannot_run(graph, state):
    graph.nodes[11]['attributes']['current_state'] = state
    assert evaluate(graph).reason_code == 'quest_not_executable'


def test_hold_is_explicit_opt_in_not_a_missing_value_default(graph):
    del graph.nodes[11]['attributes']['execution_hold']
    assert evaluate(graph).reason_code == 'quest_execution_hold'


@pytest.mark.parametrize('publication', ['draft', None])
def test_unpublished_source_is_rejected(graph, publication):
    graph.sources[graph.context.pinned_rule_refs[0]].attributes['publication_state'] = publication
    assert evaluate(graph).reason_code == 'governance_version_unpublished'


def test_ambiguous_source_is_not_selected_by_arbitrary_row_order(graph):
    graph.state.duplicate = True
    assert evaluate(graph).reason_code == 'governance_source_unavailable'


def test_revoked_source_or_task_visibility_blocks(graph):
    graph.visible.remove(101)
    assert evaluate(graph).reason_code == 'governance_source_unavailable'
    graph.visible.add(101)
    graph.visible.remove(21)
    assert evaluate(graph).reason_code == 'governance_source_unavailable'


@pytest.mark.parametrize('confidence', [0.1, None, float('nan'), True])
def test_unknown_or_low_confidence_is_not_automatic_authority(graph, confidence):
    graph.nodes[31]['attributes']['confidence'] = confidence
    assert evaluate(graph).reason_code == 'low_confidence'


def test_approval_is_preserved_as_approval_not_allow(graph):
    graph.policy['requires_approval'] = True
    assert evaluate(graph).decision == 'require_approval'


def test_high_risk_and_automatic_opt_out_are_hard_controls(graph):
    graph.nodes[11]['attributes']['risk_level'] = 'high'
    assert evaluate(graph).reason_code == 'risk_budget_exceeded'
    graph.nodes[11]['attributes']['risk_level'] = 'normal'
    graph.policy['allow_automatic'] = False
    assert evaluate(graph).reason_code == 'automatic_execution_not_allowed'


def test_evidence_must_be_verified_readable_and_scoped_to_current_work(graph):
    graph.policy['required_evidence_refs'] = ['51']
    assert evaluate(graph).reason_code == 'missing_evidence'
    graph.nodes[51]['attributes']['verification_status'] = 'supported'
    assert evaluate(graph).decision == 'allow'
    graph.state.linked = False
    assert evaluate(graph).reason_code == 'missing_evidence'


def test_unknown_controls_are_not_silently_ignored(graph):
    graph.policy['future_control'] = True
    assert evaluate(graph).reason_code == 'governance_schema_unsupported'


def test_process_does_not_authorize_a_different_command(graph):
    graph.context = replace(graph.context, command_line='task complete 21')
    assert evaluate(graph).reason_code == 'process_capability_not_allowed'


def test_domain_versions_and_pinned_refs_cannot_drift(graph):
    graph.nodes[21]['attributes']['state_version'] = 3
    assert evaluate(graph).reason_code == 'domain_state_changed'
    graph.nodes[21]['attributes']['state_version'] = 2
    graph.context = replace(graph.context, pinned_rule_refs=('test:readonly-inspection@2',))
    assert evaluate(graph).reason_code == 'governance_versions_changed'


def test_unimplemented_goal_constraints_cannot_be_ignored(graph):
    graph.nodes[41]['attributes']['constraints'] = {'downtime_minutes': 5}
    assert evaluate(graph).reason_code == 'governance_schema_unsupported'


def test_published_process_compiles_only_registered_transactional_branches(graph):
    from app.commands.registry import CommandRegistry
    from app.commands.game.look_command import LookCommand
    from app.commands.game.task.task_command import TaskCommand

    registry = CommandRegistry()
    registry.register_command(LookCommand())
    registry.register_command(TaskCommand())
    source = module.GraphQuestGovernance()
    capabilities = source.compile_capabilities(graph.session, graph.context, registry)
    assert list(capabilities) == [graph.context.pinned_rule_refs[1]]
    assert next(iter(capabilities.values())).tokens(graph.context) == ('look',)
    graph.context = replace(graph.context, command_line='task create --title unsafe')
    graph.process['command_templates'] = ['task create --title unsafe']
    assert source.compile_capabilities(graph.session, graph.context, registry) == {}


def test_unpublished_or_ambiguous_process_cannot_register_capabilities(graph):
    from app.commands.registry import CommandRegistry
    from app.commands.game.look_command import LookCommand

    registry = CommandRegistry()
    registry.register_command(LookCommand())
    graph.sources[graph.context.pinned_rule_refs[1]].attributes['publication_state'] = 'draft'
    assert module.GraphQuestGovernance().compile_capabilities(graph.session, graph.context, registry) == {}


@pytest.mark.parametrize('template', ['look {objective_id.real}', 'look {objective_id[0]}',
    'look {objective_id!r}', 'look {objective_id:1000000000}', 'look {}', 'look {unknown}', 'look {'])
def test_unsupported_template_syntax_is_rejected_in_evaluation_and_compilation(graph, template):
    from app.commands.registry import CommandRegistry
    from app.commands.game.look_command import LookCommand

    graph.process['command_templates'] = [template]
    registry = CommandRegistry()
    registry.register_command(LookCommand())
    assert evaluate(graph).reason_code == 'governance_input_invalid'
    assert module.GraphQuestGovernance().compile_capabilities(graph.session, graph.context, registry) == {}


def test_preview_never_acquires_row_locks_but_execution_evaluation_does(graph, monkeypatch):
    from app.commands.registry import CommandRegistry
    from app.commands.game.look_command import LookCommand

    queries = []
    execute = graph.session.execute
    def capture(query, params):
        queries.append(str(query).upper())
        return execute(query, params)
    monkeypatch.setattr(graph.session, 'execute', capture)
    registry = CommandRegistry()
    registry.register_command(LookCommand())
    preview = module.GraphQuestGovernance(lock_inputs=False)
    assert preview.compile_capabilities(graph.session, graph.context, registry)
    assert preview(graph.session, graph.context).decision == 'allow'
    assert preview.required_evidence_refs(graph.session, graph.context) == []
    assert not any('FOR SHARE' in sql or 'FOR UPDATE' in sql for sql in queries)
    queries.clear()
    assert evaluate(graph).decision == 'allow'
    assert any('FOR SHARE' in sql for sql in queries)
