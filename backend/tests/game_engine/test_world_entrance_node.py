"""world_entrance type and legacy portal migration (world_entry_service)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.game_engine.world_entry_service import WorldEntryService
from app.models.graph import Node, NodeType


@patch("app.game_engine.world_entry_service.flag_modified", MagicMock())
@patch("app.game_engine.world_entry_service.find_world_room_node", return_value=None)
@patch("app.game_engine.world_entry_service.root_manager")
def test_migrate_legacy_changes_type_to_world_entrance(mock_root, _mock_gate):
    root = MagicMock()
    root.id = 1
    mock_root.get_root_node.return_value = root
    nt_we = MagicMock()
    nt_we.id = 99
    legacy = MagicMock()
    legacy.type_code = "world"
    legacy.name = "hicampus"
    legacy.attributes = {
        "world_id": "hicampus",
        "portal_spawn_key": "hicampus_gate",
        "entry_hint": "enter hicampus",
    }
    session = MagicMock()
    q_nt = MagicMock()
    q_nt.filter.return_value.first.return_value = nt_we
    q_legacy = MagicMock()
    q_legacy.filter.return_value.all.return_value = [legacy]

    def query_side_effect(model):
        if model is NodeType:
            return q_nt
        if model is Node:
            return q_legacy
        m = MagicMock()
        m.filter.return_value.first.return_value = None
        m.filter.return_value.all.return_value = []
        return m

    session.query.side_effect = query_side_effect

    svc = WorldEntryService()
    svc._migrate_legacy_root_portal_to_world_entrance(session, "hicampus")

    assert legacy.type_code == "world_entrance"
    assert legacy.type_id == 99
    session.add.assert_called_with(legacy)
