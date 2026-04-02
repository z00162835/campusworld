import sys
from pathlib import Path
from unittest.mock import patch

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.game_engine.world_bridge_service import WORLD_BRIDGE_INVALID_ARGUMENT, world_bridge_service


def test_validate_bridges_requires_world_id():
    out = world_bridge_service.validate_bridges(None)
    assert out.get("ok") is False
    assert out.get("error") == WORLD_BRIDGE_INVALID_ARGUMENT


def test_validate_bridges_reports_only_unauthorized_cross_world_issues():
    with patch("app.game_engine.topology_service.world_topology_service.validate_topology") as m:
        m.return_value = {
            "ok": False,
            "issues": [
                {"code": "CORE_NODE_MISSING", "message": "x", "details": {}},
                {"code": "UNAUTHORIZED_CROSS_WORLD_RELATIONSHIP", "message": "y", "details": {}},
            ],
        }
        out = world_bridge_service.validate_bridges("w1")
    assert out["ok"] is False
    assert out["issue_count"] == 1
    assert out["issues"][0]["code"] == "UNAUTHORIZED_CROSS_WORLD_RELATIONSHIP"
