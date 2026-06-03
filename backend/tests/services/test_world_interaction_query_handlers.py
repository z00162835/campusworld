from unittest.mock import MagicMock

from app.commands.base import CommandResult
from app.services.world_interaction.command_query import CommandQueryService
from app.services.world_interaction.command_runner import CommandRunner
from app.services.world_interaction.types import WorldActor


def _actor() -> WorldActor:
    return WorldActor(user_id="1", username="tester", permissions=["player.*"], roles=["player"])


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
