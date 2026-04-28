import sys
from pathlib import Path
from unittest.mock import MagicMock

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.game_engine.subgraph_boundary import (
    bridge_enabled,
    is_authorized_cross_world_bridge,
    node_world_id,
    relationship_endpoints_span_worlds,
)


def test_node_world_id_reads_attributes():
    n = MagicMock()
    n.attributes = {"world_id": "HiCampus"}
    assert node_world_id(n) == "hicampus"


def test_relationship_endpoints_span_worlds():
    a = MagicMock()
    a.attributes = {"world_id": "w1"}
    b = MagicMock()
    b.attributes = {"world_id": "w2"}
    assert relationship_endpoints_span_worlds(a, b) is True
    assert relationship_endpoints_span_worlds(a, a) is False


def test_is_authorized_cross_world_bridge_requires_flag_and_id():
    r = MagicMock()
    r.attributes = {"cross_world_bridge": True, "bridge_id": "b1"}
    assert is_authorized_cross_world_bridge(r) is True
    r.attributes = {"cross_world_bridge": True}
    assert is_authorized_cross_world_bridge(r) is False
    r.attributes = {}
    assert is_authorized_cross_world_bridge(r) is False


def test_bridge_enabled_defaults_true():
    r = MagicMock()
    r.attributes = {"cross_world_bridge": True, "bridge_id": "x"}
    assert bridge_enabled(r) is True
    r.attributes = {"enabled": False}
    assert bridge_enabled(r) is False
