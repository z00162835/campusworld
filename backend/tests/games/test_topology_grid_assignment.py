"""Tests for HiCampus topology grid metadata assignment."""
from __future__ import annotations

from app.games.hicampus.package.topology_connect_generate import _assign_floor_map_grid


def test_assign_floor_map_grid_writes_hub_and_satellite_positions():
    hub = "floor_hub"
    on_floor = [
        {"id": hub, "floor_id": "f1", "building_id": "b1"},
        {"id": "room_north", "floor_id": "f1", "building_id": "b1"},
    ]
    floor_connects = [
        {
            "source_id": hub,
            "target_id": "room_north",
            "attributes": {"direction": "north"},
        }
    ]
    floor_row = {"id": "f1", "building_id": "b1"}
    building_row = {"id": "b1"}

    _assign_floor_map_grid(on_floor, hub, floor_connects, floor_row, building_row)

    assert on_floor[0]["map_grid_col"] == 12
    assert on_floor[0]["map_grid_row"] == 8
    assert on_floor[1]["map_grid_col"] == 12
    assert on_floor[1]["map_grid_row"] == 6
