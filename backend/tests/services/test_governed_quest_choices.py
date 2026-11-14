"""HTTP aggregation delegates governed choices to the shared runtime, not a bypass."""
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.task.permissions import Principal
from app.services.task.quest_decision import QuestGovernanceDecision
from app.services.task import task_state_machine, quest_governance, quest_execution
from app.services.world_interaction import world_interaction_service
from app.services.world_interaction import service as module
from app.services.world_interaction.types import WorldActor


def setup_scope(monkeypatch, *, mode='enforced', decision='allow', reason='fixture_pass'):
    monkeypatch.setattr(module, 'ensure_commands_initialized', lambda: None)
    root = {'governance_mode': mode, 'state_version': 1, 'risk_level': 'high',
        'policy_refs': ['test:policy@1'], 'process_refs': ['test:process@1']}
    def load(_session, *, node_id, expected_type_code):
        return {'id': node_id, 'attributes': root if node_id == 11 else {'quest_id': 11, 'state_version': 2}}
    monkeypatch.setattr(task_state_machine, 'load_node_ref', load)
    monkeypatch.setattr(module, 'can_read_semantic_node', lambda *_args, **_kwargs: True)
    monkeypatch.setattr(module, 'read_projection_cursor', lambda *_args, **_kwargs: ('7', '9'))
    class Source:
        def __init__(self, *, lock_inputs=True):
            assert lock_inputs is False
        def compile_capabilities(self, *_args):
            return {'test:process@1': object()}
        def required_evidence_refs(self, *_args):
            return ['51']
        def __call__(self, _session, context):
            return QuestGovernanceDecision(decision, reason, context.projection_revision,
                context.pinned_rule_refs, context)
    monkeypatch.setattr(quest_governance, 'GraphQuestGovernance', Source)
    return {'id': 'start_21', 'command': 'task start 21', 'targetEntityId': '21', 'requiresConfirmation': False}


def test_enforced_choice_uses_runtime_and_commits_audit_not_raw_command(monkeypatch):
    option = setup_scope(monkeypatch)
    execute = MagicMock(return_value={'success': True, 'reasonCode': 'command_completed_verification_pending'})
    monkeypatch.setattr(quest_execution, 'QuestActionExecutor', lambda **_kwargs: SimpleNamespace(execute=execute))
    monkeypatch.setattr(world_interaction_service, 'refresh_interaction_state', lambda *_args: {
        'decision_center': {'decisionEvents': [{'id': 'task_21', 'options': [option]}]}})
    monkeypatch.setattr(world_interaction_service, '_state_patch_after_result', lambda _s, _a, result, **_kwargs: {
        'success': result.success, 'result': {'summary': result.message, 'status': 'completed'}, 'state_patch': {}})
    raw = MagicMock()
    monkeypatch.setattr(world_interaction_service, 'execute_command', raw)
    session = MagicMock()
    response = world_interaction_service.execute_decision_action(session,
        WorldActor(user_id='1', username='u', roles=[], permissions=['task.update']), 'task_21', 'start_21')
    assert response['success']
    assert response['result']['summaryKey'].endswith('command_completed_verification_pending')
    context = execute.call_args.kwargs['context']
    assert context.quest_id == 11 and context.objective_id == 21
    assert context.actor.kind == 'user'
    assert context.objective_state_version == 2
    raw.assert_not_called()
    session.commit.assert_called_once()


def test_legacy_choice_keeps_existing_command_path(monkeypatch):
    option = setup_scope(monkeypatch, mode='legacy')
    actor = WorldActor(user_id='1', username='u', roles=[], permissions=['task.update'])
    assert world_interaction_service._execute_governed_task_choice(MagicMock(), actor, option) is None


def test_missing_evidence_preview_is_not_a_clear_gate(monkeypatch):
    option = setup_scope(monkeypatch, decision='deny', reason='missing_evidence')
    principal = Principal(id=1, kind='user', permissions=frozenset({'task.update'}))
    world_interaction_service._decorate_governed_task_choices(MagicMock(), principal, [option, option])
    assert option['gateStatus'] == 'evidence_required'
    assert option['gateReasonCode'] == 'missing_evidence'
    assert option['requiredEvidenceRefs'] == ['51']
    assert option['consequenceProvenanceRefs'] == ['test:policy@1', 'test:process@1']
    assert option['riskLevel'] == 'high'
    assert option['requiresConfirmation'] is True


def test_approval_preview_cannot_be_converted_to_clear_by_command_permission(monkeypatch):
    option = setup_scope(monkeypatch, decision='require_approval', reason='approval_required')
    principal = Principal(id=1, kind='user', permissions=frozenset({'*'}))
    world_interaction_service._decorate_governed_task_choices(MagicMock(), principal, [option])
    assert option['gateStatus'] == 'approval_required'
