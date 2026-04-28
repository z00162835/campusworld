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
    assert "world <list|install|uninstall|reload|status|validate|repair|content>" in out.message
    assert "bridge" in out.message


def test_world_command_denies_without_sub_permission():
    cmd = WorldCommand()
    out = cmd.execute(_ctx(["admin.system_notice"]), ["list"])
    assert not out.success
    assert out.error == "WORLD_FORBIDDEN"


def test_world_command_validate_placeholder():
    cmd = WorldCommand()
    from unittest.mock import patch

    with patch("app.commands.game.world_command.game_engine_manager.list_games", return_value=["hicampus"]):
        with patch("app.commands.game.world_command.world_topology_service.validate_topology") as m:
            m.return_value = {"ok": True, "issue_count": 0, "issues": []}
            out = cmd.execute(_ctx(["admin.world.maintain"]), ["validate", "hicampus", "--dry-run"])
    assert out.success
    assert "world validate passed" in out.message
    assert out.data["report"]["ok"] is True


def test_world_command_repair_placeholder():
    cmd = WorldCommand()
    from unittest.mock import patch

    with patch("app.commands.game.world_command.game_engine_manager.list_games", return_value=["hicampus"]):
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
    assert "display_name" in item
    assert "hicampus" in out.message
    assert "world_id" in out.message
    assert "(total=1)" in out.message


def test_world_command_install_resolves_case_insensitive_id():
    from unittest.mock import patch

    cmd = WorldCommand()
    structured = {
        "ok": True,
        "world_id": "hicampus",
        "status_after": "installed",
        "message": "ok",
        "details": {},
    }
    with patch("app.commands.game.world_command.game_engine_manager.list_games", return_value=["hicampus"]):
        with patch("app.commands.game.world_command.game_engine_manager.load_game", return_value=structured) as m_load:
            with patch("app.commands.game.world_command.game_engine_manager.get_engine", return_value=None):
                with patch("app.commands.game.world_command.world_entry_service.sync_world_entry_visibility"):
                    out = cmd.execute(_ctx(["admin.world.manage"]), ["install", "HiCampus"])
    assert out.success
    m_load.assert_called_once_with("hicampus")


def test_world_command_resolve_ambiguous_display_name():
    from unittest.mock import MagicMock, patch

    cmd = WorldCommand()
    mock_eng = MagicMock()
    mock_loader = MagicMock()
    mock_eng.loader = mock_loader
    with patch("app.commands.game.world_command.game_engine_manager.list_games", return_value=["w1", "w2"]):
        with patch("app.commands.game.world_command.game_engine_manager.get_engine", return_value=mock_eng):
            with patch.object(
                WorldCommand,
                "_resolve_world_path",
                return_value={"resolved_path": "/fake/pkg", "source_type": "builtin"},
            ):
                with patch(
                    "app.commands.game.world_command._read_manifest_brief",
                    return_value={"display_name": "SameLabel"},
                ):
                    wid, err = cmd._resolve_world_ref("SameLabel")
    assert wid is None
    assert err and "ambiguous" in err.lower()


def test_world_command_unknown_world_returns_not_found():
    from unittest.mock import patch

    cmd = WorldCommand()
    with patch("app.commands.game.world_command.game_engine_manager.list_games", return_value=[]):
        with patch("app.commands.game.world_command.game_engine_manager.get_engine", return_value=None):
            out = cmd.execute(_ctx(["admin.world.manage"]), ["install", "nope"])
    assert not out.success
    assert out.error == "WORLD_NOT_FOUND"


def test_world_command_status_returns_runtime_and_path():
    from unittest.mock import patch

    cmd = WorldCommand()
    with patch("app.commands.game.world_command.game_engine_manager.list_games", return_value=["hicampus"]):
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
    with patch("app.commands.game.world_command.game_engine_manager.list_games", return_value=["hicampus"]):
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
    with patch("app.commands.game.world_command.game_engine_manager.list_games", return_value=["hicampus"]):
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
    with patch("app.commands.game.world_command.game_engine_manager.list_games", return_value=["hicampus"]):
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

    with patch("app.commands.game.world_command.game_engine_manager.list_games", return_value=["hicampus"]):
        with patch("app.commands.game.world_command.world_topology_service.validate_topology") as m:
            m.return_value = {"ok": False, "issue_count": 2, "issues": [{"code": "X"}, {"code": "Y"}]}
            out = cmd.execute(_ctx(["admin.world.maintain"]), ["validate", "hicampus"])
    assert not out.success
    assert out.error == "WORLD_TOPOLOGY_INVALID"
    assert out.data["report"]["issue_count"] == 2


def test_world_command_repair_dry_run_force_combined_still_dry_run():
    from unittest.mock import patch

    cmd = WorldCommand()
    with patch("app.commands.game.world_command.game_engine_manager.list_games", return_value=["hicampus"]):
        with patch("app.commands.game.world_command.world_topology_service.repair_topology") as m:
            m.return_value = {"planned_actions": [], "applied_actions": [], "ok": True}
            out = cmd.execute(_ctx(["admin.world.maintain"]), ["repair", "hicampus", "--dry-run", "--force"])
    assert out.success
    args, kwargs = m.call_args
    assert kwargs["dry_run"] is True
    assert kwargs["force"] is True


def test_world_bridge_add_denied_without_manage_permission():
    from unittest.mock import patch

    cmd = WorldCommand()
    out = cmd.execute(
        _ctx(["admin.world.bridge.read"]),
        ["bridge", "add", "w1", "r1", "north", "w2", "r2"],
    )
    assert not out.success
    assert out.error == "WORLD_BRIDGE_PERMISSION_DENIED"


def test_world_bridge_list_ok_with_read_permission():
    from unittest.mock import patch

    cmd = WorldCommand()
    with patch("app.commands.game.world_command.world_bridge_service.list_bridges") as m:
        m.return_value = {"ok": True, "bridges": [], "total": 0}
        out = cmd.execute(_ctx(["admin.world.bridge.read"]), ["bridge", "list"])
    assert out.success
    assert out.data["total"] == 0


def test_world_bridge_add_calls_service_with_manage_permission():
    from unittest.mock import patch

    cmd = WorldCommand()
    with patch("app.commands.game.world_command.world_bridge_service.add_bridge") as m:
        m.return_value = {"ok": True, "bridge_id": "b1", "message": "bridge created", "status": "applied"}
        out = cmd.execute(
            _ctx(["admin.world.bridge.manage"]),
            ["bridge", "add", "w1", "r1", "north", "w2", "r2", "--dry-run"],
        )
    assert out.success
    _, kwargs = m.call_args
    assert kwargs.get("dry_run") is True


def test_world_bridge_add_same_world_surface_service_error():
    from unittest.mock import patch

    cmd = WorldCommand()
    with patch("app.commands.game.world_command.world_bridge_service.add_bridge") as m:
        m.return_value = {
            "ok": False,
            "error": "WORLD_BRIDGE_CROSS_BOUNDARY_VIOLATION",
            "message": "bridge must span two different worlds",
        }
        out = cmd.execute(
            _ctx(["admin.world.bridge.manage"]),
            ["bridge", "add", "w1", "r1", "north", "w1", "r2"],
        )
    assert not out.success
    assert out.error == "WORLD_BRIDGE_CROSS_BOUNDARY_VIOLATION"


def test_world_bridge_validate_with_issues_returns_boundary_violation():
    from unittest.mock import patch

    cmd = WorldCommand()
    with patch("app.commands.game.world_command.world_bridge_service.validate_bridges") as m:
        m.return_value = {
            "ok": False,
            "world_id": "w1",
            "issues": [{"code": "UNAUTHORIZED_CROSS_WORLD_RELATIONSHIP", "message": "x", "details": {}}],
            "issue_count": 1,
            "summary": {},
        }
        out = cmd.execute(_ctx(["admin.world.bridge.read"]), ["bridge", "validate", "w1"])
    assert not out.success
    assert out.error == "WORLD_BOUNDARY_VIOLATION"
    assert out.data["issue_count"] == 1

