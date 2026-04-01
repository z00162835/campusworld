import sys
from pathlib import Path
from unittest.mock import MagicMock

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.commands.base import CommandContext
from app.commands.game.world_command import WorldCommand


def _ctx(perms):
    return CommandContext(
        user_id="1",
        username="admin",
        session_id="s1",
        permissions=list(perms),
        game_state={},
        db_session=MagicMock(),
    )


def test_world_command_usage_when_missing_args():
    cmd = WorldCommand()
    out = cmd.execute(_ctx(["admin.world.*"]), [])
    assert not out.success
    assert "world <list|install|uninstall|reload|status|validate|repair>" in out.message


def test_world_command_denies_without_sub_permission():
    cmd = WorldCommand()
    out = cmd.execute(_ctx(["admin.system_notice"]), ["list"])
    assert not out.success
    assert out.error == "WORLD_FORBIDDEN"


def test_world_command_validate_placeholder():
    cmd = WorldCommand()
    from unittest.mock import patch

    with patch("app.commands.game.world_command.world_topology_service.validate_topology") as m:
        m.return_value = {"ok": True, "issue_count": 0, "issues": []}
        out = cmd.execute(_ctx(["admin.world.maintain"]), ["validate", "hicampus", "--dry-run"])
    assert out.success
    assert "world validate passed" in out.message
    assert out.data["report"]["ok"] is True


def test_world_command_repair_placeholder():
    cmd = WorldCommand()
    from unittest.mock import patch

    with patch("app.commands.game.world_command.world_topology_service.repair_topology") as m:
        m.return_value = {"planned_actions": [{"action": "x"}], "applied_actions": [], "ok": False}
        out = cmd.execute(_ctx(["admin.world.maintain"]), ["repair", "hicampus", "--dry-run", "--force"])
    assert not out.success
    assert "world repair dry-run ready" in out.message
    assert len(out.data["report"]["planned_actions"]) == 1


def test_world_command_list_has_path_observability():
    from unittest.mock import patch

    cmd = WorldCommand()
    with patch("app.commands.game.world_command.game_engine_manager.list_games", return_value=["hicampus"]):
        with patch("app.commands.game.world_command.game_engine_manager.get_engine", return_value=None):
            out = cmd.execute(_ctx(["admin.world.read"]), ["list"])
    assert out.success
    assert out.data["total"] == 1
    item = out.data["items"][0]
    assert item["world_id"] == "hicampus"
    assert "resolved_path" in item
    assert "source_type" in item


def test_world_command_status_returns_runtime_and_path():
    from unittest.mock import patch

    cmd = WorldCommand()
    with patch("app.commands.game.world_command.game_engine_manager.get_game_status", return_value={"state": "x"}):
        with patch("app.commands.game.world_command.game_engine_manager.get_engine", return_value=None):
            out = cmd.execute(_ctx(["admin.world.read"]), ["status", "hicampus"])
    assert out.success
    assert out.data["world_id"] == "hicampus"
    assert "runtime_state" in out.data
    assert "resolved_path" in out.data
    assert "source_type" in out.data


def test_world_command_install_wraps_structured_result():
    from unittest.mock import patch

    cmd = WorldCommand()
    structured = {
        "ok": True,
        "world_id": "hicampus",
        "job_id": "j-1",
        "status_before": "not_installed",
        "status_after": "installed",
        "error_code": None,
        "message": "world loaded",
        "details": {},
    }
    with patch("app.commands.game.world_command.game_engine_manager.load_game", return_value=structured):
        with patch("app.commands.game.world_command.game_engine_manager.get_engine", return_value=None):
            with patch("app.commands.game.world_command.world_entry_service.sync_world_entry_visibility") as m_sync:
                out = cmd.execute(_ctx(["admin.world.manage"]), ["install", "hicampus"])
    assert out.success
    assert out.data["world_id"] == "hicampus"
    assert out.data["status_after"] == "installed"
    m_sync.assert_called_once_with("hicampus", enabled=True)


def test_world_command_uninstall_syncs_entry_hidden():
    from unittest.mock import patch

    cmd = WorldCommand()
    structured = {
        "ok": True,
        "world_id": "hicampus",
        "message": "world unloaded",
        "details": {},
    }
    with patch("app.commands.game.world_command.game_engine_manager.unload_game", return_value=structured):
        with patch("app.commands.game.world_command.game_engine_manager.get_engine", return_value=None):
            with patch("app.commands.game.world_command.world_entry_service.sync_world_entry_visibility") as m_sync:
                out = cmd.execute(_ctx(["admin.world.manage"]), ["uninstall", "hicampus"])
    assert out.success
    m_sync.assert_called_once_with("hicampus", enabled=False)


def test_world_command_install_failure_keeps_structured_payload():
    from unittest.mock import patch

    cmd = WorldCommand()
    structured = {
        "ok": False,
        "world_id": "hicampus",
        "job_id": "j-2",
        "status_before": "not_installed",
        "status_after": "failed",
        "error_code": "WORLD_LOAD_FAILED",
        "message": "world load failed",
        "details": {"reason": "x"},
    }
    with patch("app.commands.game.world_command.game_engine_manager.load_game", return_value=structured):
        with patch("app.commands.game.world_command.game_engine_manager.get_engine", return_value=None):
            out = cmd.execute(_ctx(["admin.world.manage"]), ["install", "hicampus"])
    assert not out.success
    assert out.error == "WORLD_LOAD_FAILED"
    assert out.data["world_id"] == "hicampus"
    assert out.data["status_after"] == "failed"


def test_world_command_validate_with_issues_returns_error_with_report():
    cmd = WorldCommand()
    from unittest.mock import patch

    with patch("app.commands.game.world_command.world_topology_service.validate_topology") as m:
        m.return_value = {"ok": False, "issue_count": 2, "issues": [{"code": "X"}, {"code": "Y"}]}
        out = cmd.execute(_ctx(["admin.world.maintain"]), ["validate", "hicampus"])
    assert not out.success
    assert out.error == "WORLD_TOPOLOGY_INVALID"
    assert out.data["report"]["issue_count"] == 2


def test_world_command_repair_dry_run_force_combined_still_dry_run():
    from unittest.mock import patch

    cmd = WorldCommand()
    with patch("app.commands.game.world_command.world_topology_service.repair_topology") as m:
        m.return_value = {"planned_actions": [], "applied_actions": [], "ok": True}
        out = cmd.execute(_ctx(["admin.world.maintain"]), ["repair", "hicampus", "--dry-run", "--force"])
    assert out.success
    args, kwargs = m.call_args
    assert kwargs["dry_run"] is True
    assert kwargs["force"] is True

