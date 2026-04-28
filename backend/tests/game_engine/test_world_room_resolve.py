import sys
from pathlib import Path
from unittest.mock import MagicMock

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.game_engine.world_room_resolve import find_world_room_node


def test_find_world_room_node_returns_none_when_empty_ids():
    session = MagicMock()
    assert find_world_room_node(session, "", "x") is None
    assert find_world_room_node(session, "w", "") is None
    session.query.assert_not_called()
