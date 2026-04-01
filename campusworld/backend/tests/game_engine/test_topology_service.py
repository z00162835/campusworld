import sys
from pathlib import Path
from unittest.mock import patch

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

