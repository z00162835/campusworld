import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.game_engine.topology_service import TopologyIssue, WorldTopologyService


def test_validate_topology_contract_uses_issue_count():
    svc = WorldTopologyService()
    with patch.object(svc, "_collect_issues", return_value=[]):
        out = svc.validate_topology("hicampus")
    assert out["ok"] is True
    assert out["issue_count"] == 0
    assert out["world_id"] == "hicampus"


def test_repair_topology_dry_run_returns_plan_without_apply():
    svc = WorldTopologyService()
    issues = [
        TopologyIssue(
            code="CONNECTS_TO_REVERSE_MISSING",
            message="x",
            details={"source_id": 1, "target_id": 2},
        )
    ]
    with patch.object(svc, "_collect_issues", return_value=issues):
        out = svc.repair_topology("hicampus", dry_run=True, force=False)
    assert out["dry_run"] is True
    assert len(out["planned_actions"]) == 1
    assert out["applied_actions"] == []


def test_repair_topology_force_gate_without_force_skips():
    svc = WorldTopologyService()
    issues = [
        TopologyIssue(
            code="CONNECTS_TO_REVERSE_MISSING",
            message="x",
            details={"source_id": 1, "target_id": 2},
        )
    ]
    with patch.object(svc, "_collect_issues", return_value=issues):
        out = svc.repair_topology("hicampus", dry_run=False, force=False)
    assert len(out["planned_actions"]) == 1
    assert out["applied_actions"] == []
    assert len(out["skipped_actions"]) == 1
    assert out["skipped_actions"][0]["reason"] == "force_required"
    assert out["ok"] is False


def test_topology_unknown_world_has_empty_required_core_rooms():
    svc = WorldTopologyService()
    profile = svc._get_profile("demo_world")
    assert profile["required_core_rooms"] == []


def test_topology_hicampus_world_has_core_room_profile():
    svc = WorldTopologyService()
    profile = svc._get_profile("hicampus")
    assert "hicampus_gate" in profile["required_core_rooms"]


def test_build_repair_actions_includes_disable_unauthorized():
    svc = WorldTopologyService()
    issues = [
        TopologyIssue(
            code="UNAUTHORIZED_CROSS_WORLD_RELATIONSHIP",
            message="x",
            details={"relationship_id": 5},
        )
    ]
    plan = svc._build_repair_actions(issues)
    assert any(a.get("action") == "disable_unauthorized_cross_world_link" for a in plan)
    assert any(a.get("relationship_id") == 5 for a in plan)


def test_repair_dry_run_plans_disable_unauthorized_cross_world():
    svc = WorldTopologyService()
    issues = [
        TopologyIssue(
            code="UNAUTHORIZED_CROSS_WORLD_RELATIONSHIP",
            message="cross",
            details={"relationship_id": 42},
        )
    ]
    with patch.object(svc, "_collect_issues", return_value=issues):
        out = svc.repair_topology("w1", dry_run=True, force=False)
    names = [a.get("action") for a in out["planned_actions"]]
    assert "disable_unauthorized_cross_world_link" in names


def test_collect_account_session_issues_room_missing():
    svc = WorldTopologyService()
    acc = SimpleNamespace(id=99, attributes={"active_world": "w1", "world_location": "r_pkg"})
    account_holder = [[acc]]
    session = MagicMock()

    def query_side_effect(_model):
        m = MagicMock()
        nonlocal account_holder
        if account_holder[0] is not None:
            m.filter.return_value.all.return_value = account_holder[0]
            account_holder[0] = None
            return m
        m.filter.return_value.first.return_value = None
        return m

    session.query.side_effect = query_side_effect
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = session
    mock_cm.__exit__.return_value = None
    with patch("app.game_engine.topology_service.db_session_context", return_value=mock_cm):
        issues = svc._collect_account_session_issues("w1")
    assert len(issues) == 1
    assert issues[0].code == "SESSION_WORLD_LOCATION_ROOM_MISSING"
    assert issues[0].details["account_id"] == 99
    assert issues[0].details["world_location"] == "r_pkg"


def test_collect_account_session_issues_world_mismatch():
    svc = WorldTopologyService()
    acc = SimpleNamespace(id=7, attributes={"active_world": "w1", "world_location": "r_pkg"})
    room = SimpleNamespace(attributes={"world_id": "w2", "package_node_id": "r_pkg"})
    account_holder = [[acc]]
    session = MagicMock()

    def query_side_effect(_model):
        m = MagicMock()
        nonlocal account_holder
        if account_holder[0] is not None:
            m.filter.return_value.all.return_value = account_holder[0]
            account_holder[0] = None
            return m
        m.filter.return_value.first.return_value = room
        return m

    session.query.side_effect = query_side_effect
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = session
    mock_cm.__exit__.return_value = None
    with patch("app.game_engine.topology_service.db_session_context", return_value=mock_cm):
        issues = svc._collect_account_session_issues("w1")
    assert len(issues) == 1
    assert issues[0].code == "SESSION_ACTIVE_WORLD_LOCATION_MISMATCH"
    assert issues[0].details["room_world_id"] == "w2"
    assert issues[0].details["active_world"] == "w1"

