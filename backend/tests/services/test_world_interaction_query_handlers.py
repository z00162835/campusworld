from unittest.mock import MagicMock
import pytest
from types import SimpleNamespace

from app.commands.base import CommandResult
from app.services.world_interaction.command_query import CommandQueryService
from app.services.world_interaction.command_runner import CommandRunOptions, CommandRunner
from app.services.world_interaction.service import WorldInteractionService
from app.services.world_interaction.types import WorldActor
from app.services.task.user_task_queue import QueueTaskRow
from app.services.world_interaction import world_interaction_service
from app.services.world_interaction import service as world_interaction_module
from app.services.task.errors import OptimisticLockError, ReferenceNotFound


def _actor() -> WorldActor:
    return WorldActor(user_id="1", username="tester", permissions=["player.*"], roles=["player"])


def test_choice_contract_preserves_governance_metadata_without_inventing_defaults():
    option = WorldInteractionService._option(
        'inspect', 'Inspect', 'primary', 'execute_command',
        label_key='actions.inspect', label_params={'name': 'AHU'},
        consequence_kind='predicted', consequence_confidence=0.7,
        consequence_provenance_refs=['case:7'], risk_level='high',
        required_evidence_refs=['observation:3'], gate_status='evidence_required',
        reversible=False, affected_entity_refs=['device:9'],
    )
    assert option['labelParams'] == {'name': 'AHU'}
    assert option['consequenceConfidence'] == 0.7
    assert option['consequenceProvenanceRefs'] == ['case:7']
    assert option['requiredEvidenceRefs'] == ['observation:3']
    assert option['gateStatus'] == 'evidence_required'
    assert option['riskLevel'] == 'high'
    assert option['reversible'] is False
    assert option['requiresConfirmation'] is True
    assert option['affectedEntityRefs'] == ['device:9']
    unknown = WorldInteractionService._option('look', 'Look', 'quiet', 'execute_command')
    assert unknown['consequenceConfidence'] is None
    assert unknown['riskLevel'] is None
    assert unknown['gateStatus'] is None
    assert unknown['requiresConfirmation'] is False


def test_all_queue_task_options_supply_localized_label_keys():
    for state, expected in [('open', 'claim'), ('claimed', 'start'), ('in_progress', 'complete'), ('done', 'view')]:
        row = SimpleNamespace(id=21, state=state, visibility='pool_open', assignee_kind='pool')
        option = world_interaction_service._options_for_queue_task(row)[0]
        assert option['labelKey'] == f'worldInteraction.decision.action.{expected}'
        assert option['labelParams'] == {}


def test_command_query_slash_command_returns_state_patch():
    def fake_run(session, actor, command_line):
        assert command_line == "look"
        return CommandResult.success_result("You see the room.")


    def fake_patch(session, actor, result):
        return {"state_patch": {"currentSpaceId": "10"}, "command_result": {"success": True, "message": result.message}}

    service = CommandQueryService(run_command=fake_run, search=MagicMock(), build_patch=fake_patch)
    payload = service.run(MagicMock(), _actor(), "/look")
    assert payload["mode"] == "command"
    assert payload["state_patch"]["currentSpaceId"] == "10"


def test_command_query_bare_word_runs_command_not_search():
    search_mock = MagicMock()

    def fake_run(session, actor, command_line):
        assert command_line == "look"
        return CommandResult.success_result("You see the room.")

    def fake_patch(session, actor, result):
        return {"state_patch": {}, "command_result": {"success": True, "message": result.message}}

    service = CommandQueryService(run_command=fake_run, search=search_mock, build_patch=fake_patch)
    payload = service.run(MagicMock(), _actor(), "look")
    assert payload["command_result"]["message"] == "You see the room."
    search_mock.assert_not_called()


def test_command_query_text_search_delegates_to_search():
    def fake_search(session, actor, query):
        assert query == "gate"
        return {"summary": "Found 1", "results": [{"entity_id": "1"}], "suggested_actions": []}

    service = CommandQueryService(
        run_command=MagicMock(),
        search=fake_search,
        build_patch=MagicMock(),
    )
    payload = service.run(MagicMock(), _actor(), "search gate")
    assert payload["results"][0]["entity_id"] == "1"


def test_command_runner_rejects_empty_command_line():
    runner = CommandRunner()
    result = runner.run(MagicMock(), _actor(), "   ")
    assert result.success is False
    assert result.error == "command.empty"


def test_command_runner_passes_quest_context_through_agent_dispatch(monkeypatch):
    from app.commands import at_agent_dispatch

    result = CommandResult.success_result("Companion response")
    def dispatch(command_line, context):
        assert command_line == "@companion quest-context Help with the Quest"
        assert context.metadata['quest_conversation_context']['quest_node_id'] == 11
        assert context.metadata['aico_client_thread_id'] == 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
        return result

    monkeypatch.setattr(at_agent_dispatch, 'try_dispatch_at_line', dispatch)
    runner = CommandRunner()
    actual = runner.run(
        MagicMock(),
        _actor(),
        "@companion quest-context Help with the Quest",
        options=CommandRunOptions(
            aico_client_thread_id='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
            quest_conversation_context={'quest_node_id': 11},
        ),
    )

    assert actual is result


def test_quest_conversation_context_requires_current_projection_revision(monkeypatch):
    service = WorldInteractionService()
    monkeypatch.setattr(service, '_get_user_node', lambda *_args, **_kwargs: SimpleNamespace(id=1))
    monkeypatch.setattr(world_interaction_module, 'read_projection_cursor', lambda *_args, **_kwargs: ('9', '3'))

    try:
        service.validate_quest_conversation_context(
            MagicMock(),
            _actor(),
            {'quest_id': 11, 'projection_revision': '8'},
        )
    except OptimisticLockError:
        pass
    else:
        raise AssertionError('stale Quest conversation context must be rejected')


@pytest.mark.parametrize('task_visible', [True, False])
def test_quest_dialogue_uses_task_visibility_not_semantic_ownership_for_objectives(monkeypatch, task_visible):
    service = WorldInteractionService()
    monkeypatch.setattr(service, '_get_user_node', lambda *_args, **_kwargs: SimpleNamespace(id=1))
    monkeypatch.setattr(world_interaction_module, 'read_projection_cursor', lambda *_args, **_kwargs: ('9', '3'))
    monkeypatch.setattr(world_interaction_module, 'can_read_semantic_node',
        lambda _session, *, node_id, actor: node_id != 21)
    monkeypatch.setattr(world_interaction_module, 'visible_task_ids',
        lambda _session, _actor, _ids: {21} if task_visible else set())
    monkeypatch.setattr(world_interaction_module, 'show_quest', lambda **_kwargs: {
        'quest': {'title': 'Quest'}, 'objectives': [{'task_id': 21, 'title': 'Pool-visible task'}],
    })
    session = MagicMock()
    session.execute.return_value.first.return_value = (1,)
    payload = {'quest_id': 11, 'objective_id': 21, 'projection_revision': '9'}
    if task_visible:
        context = service.validate_quest_conversation_context(session, _actor(), payload)
        assert context['objective_node_id'] == 21
        assert context['objective_title'] == 'Pool-visible task'
    else:
        with pytest.raises(ReferenceNotFound):
            service.validate_quest_conversation_context(session, _actor(), payload)


def test_foreground_quest_hud_uses_aggregate_objective_progress():
    service = WorldInteractionService()
    objective = QueueTaskRow(
        id=21,
        state="in_progress",
        title="Inspect bearing",
        priority="normal",
        pool_key=None,
        visibility="assigned",
        assignee_kind="user",
        quest_id=11,
        quest_title="Restore AHU",
    )
    action = service._options_for_queue_task(objective)[0]

    card = service._active_task_from_queue(
        [objective],
        action,
        quest_projection={"id": "11", "progress": {"percent": 67}},
    )

    assert card is not None
    assert card["id"] == "task_21"
    assert card["progress"] == 67


def test_context_summary_reuses_the_foreground_hud_projection(monkeypatch):
    service = WorldInteractionService()
    monkeypatch.setattr(
        "app.services.world_interaction.service.list_for_principal",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "app.services.world_interaction.service.last_handled_task",
        lambda *_args, **_kwargs: None,
    )
    active_task = {
        "id": "task_21",
        "title": "Restore AHU",
        "summary": "State: in_progress",
        "progress": 67,
        "currentStep": {"title": "Inspect bearing"},
    }

    summary = service._context_summary(
        MagicMock(),
        MagicMock(),
        MagicMock(id=7),
        {"agentPresences": []},
        "hicampus",
        active_task=active_task,
    )

    assert summary["activeTask"] == {
        "id": "task_21",
        "title": "Restore AHU",
        "currentStep": "Inspect bearing",
        "progress": 67,
    }


def test_mutating_world_command_advances_projection_revision(monkeypatch):
    session = MagicMock()
    actor = _actor()
    monkeypatch.setattr(
        world_interaction_service._command_runner,
        "run",
        lambda *_args, **_kwargs: CommandResult.success_result("entered"),
    )
    monkeypatch.setattr(
        "app.services.world_interaction.service.resolve_command_tool_semantics",
        lambda *_args, **_kwargs: MagicMock(interaction_profile="mutate"),
    )
    monkeypatch.setattr(
        world_interaction_service,
        "_get_user_node",
        lambda *_args, **_kwargs: MagicMock(id=1),
    )
    record = MagicMock()
    monkeypatch.setattr("app.services.world_interaction.service.record_projection_change", record)

    result = world_interaction_service.execute_command(session, actor, "enter hicampus")

    assert result.success is True
    record.assert_called_once()
    session.commit.assert_called_once()


def test_mutating_command_with_revision_commits_without_duplicate_event(monkeypatch):
    session = MagicMock()
    result = CommandResult.success_result('tracked', data={'projection_revision': '8'})
    monkeypatch.setattr(world_interaction_service._command_runner, 'run', lambda *_args: result)
    monkeypatch.setattr(world_interaction_module, 'resolve_command_tool_semantics',
                        lambda *_args, **_kwargs: SimpleNamespace(interaction_profile='mutate'))
    record = MagicMock()
    monkeypatch.setattr(world_interaction_module, 'record_projection_change', record)

    assert world_interaction_service.execute_command(session, _actor(), 'quest track 11') is result
    session.commit.assert_called_once()
    record.assert_not_called()


def test_read_only_and_failed_commands_do_not_commit(monkeypatch):
    record = MagicMock()
    monkeypatch.setattr(world_interaction_module, 'record_projection_change', record)
    monkeypatch.setattr(world_interaction_module, 'resolve_command_tool_semantics',
                        lambda *_args, **_kwargs: SimpleNamespace(interaction_profile='inspect'))
    for result in (CommandResult.success_result('shown'), CommandResult.error_result('denied')):
        session = MagicMock()
        monkeypatch.setattr(world_interaction_service._command_runner, 'run', lambda *_args: result)
        assert world_interaction_service.execute_command(session, _actor(), 'quest show 11') is result
        session.commit.assert_not_called()
    record.assert_not_called()
