"""Room exit list: merge room_exits attrs with graph connects_to projection."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.commands.game.look_command import (
    _merge_room_exit_labels_from_attrs_and_graph,
    _sort_room_exit_labels,
)


def test_sort_room_exit_labels_compass_order():
    assert _sort_room_exit_labels(["south", "north", "east"]) == ["north", "east", "south"]


def test_merge_attrs_and_graph_dedupes_normalized():
    ra = {"room_exits": {"n": {}, "east": {}}}
    graph = ["south", "north"]
    out = _merge_room_exit_labels_from_attrs_and_graph(ra, graph)
    assert out == ["north", "east", "south"]
