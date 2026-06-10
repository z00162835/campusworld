"""Unit tests for semantic map layout and focus map builder."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.world_interaction.map_layout import (
    CENTER_X,
    CENTER_Y,
    assign_neighbor_positions,
    compass_position,
)
from app.services.world_interaction.semantic_map_service import (
    apply_event_space_ids,
    build_building_focus_map,
    build_campus_focus_map,
    build_floor_focus_map,
    build_focus_map,
    build_map_query_patch,
    build_room_focus_map,
)


def test_compass_position_north_is_above_center():
    x, y = compass_position("north")
    assert x == CENTER_X
    assert y == CENTER_Y - 28


def test_assign_neighbor_positions_planar_directions():
    entries = [("north", "2"), ("east", "3")]
    positions = assign_neighbor_positions(entries)
    assert positions[0] == (CENTER_X, CENTER_Y - 28)
    assert positions[1] == (CENTER_X + 28, CENTER_Y)


def test_build_room_focus_map_neighbor_links_no_go_commands():
    location = SimpleNamespace(
        id=1,
        type_code="room",
        name="Hub",
        location_id=None,
        attributes={"display_name": "Hub"},
        tags=[],
    )
    target = SimpleNamespace(
        id=2,
        type_code="room",
        name="North Room",
        attributes={"display_name": "North Room", "room_short_description": "Ahead"},
        tags=[],
    )
    rel = SimpleNamespace(id=99, source_id=1, target_id=2, attributes={"direction": "north"}, target_role=None)

    session = MagicMock()
    rel_query = MagicMock()
    rel_query.filter.return_value.limit.return_value.all.return_value = [rel]
    node_query = MagicMock()
    node_query.filter.return_value.all.return_value = [target]
    agent_query = MagicMock()
    agent_query.filter.return_value.limit.return_value.all.return_value = []

    def query_side_effect(model):
        if getattr(model, "__name__", "") == "Relationship":
            return rel_query
        return node_query if model.__name__ == "Node" else MagicMock()

    session.query.side_effect = query_side_effect

    with patch(
        "app.services.world_interaction.semantic_map_service.connects_to_exits_from_room",
        return_value=[
            {
                "direction": "north",
                "target_id": 2,
                "target_display_name": "North Room",
                "target_short_desc": "Ahead",
            }
        ],
    ):
        payload = build_room_focus_map(session, location)

    assert payload["viewLayer"] == "room"
    assert payload["orientation"] == "north-up"
    assert len(payload["nodes"]) == 2
    assert payload["nodes"][0]["status"] == "current"
    north_node = next(n for n in payload["nodes"] if n["id"] == "2")
    assert north_node["y"] < CENTER_Y
    assert payload["edges"][0]["direction"] == "north"
    assert payload["neighborLinks"][0]["direction"] == "north"
    assert payload["neighborLinks"][0]["targetId"] == "2"
    assert "command" not in payload["neighborLinks"][0]


def _room_node(node_id: int, *, floor_id: int = 10, name: str = "Room", grid: bool = False) -> SimpleNamespace:
    attrs = {"display_name": name, "floor_id": "pkg-floor"}
    if grid:
        attrs.update({"map_grid_col": 4, "map_grid_row": 2, "map_grid_span_w": 1, "map_grid_span_h": 1})
    return SimpleNamespace(
        id=node_id,
        type_code="room",
        name=name,
        location_id=floor_id,
        attributes=attrs,
        tags=[],
    )


def test_build_floor_focus_map_uses_grid_layout():
    location = _room_node(1, name="Current")
    floor = SimpleNamespace(id=10, type_code="building_floor", name="3F", location_id=20, attributes={"display_name": "3F", "package_node_id": "pkg-floor"}, tags=[])
    building = SimpleNamespace(id=20, type_code="building", name="F3", location_id=30, attributes={"display_name": "F3 Tower", "package_node_id": "pkg-b"}, tags=[])
    world = SimpleNamespace(id=30, type_code="world", name="HiCampus", location_id=None, attributes={"display_name": "HiCampus", "world_id": "hicampus"}, tags=[])
    room_a = _room_node(2, name="Lab", grid=True)
    room_b = _room_node(3, name="Hall", grid=True)

    session = MagicMock()

    with patch(
        "app.services.world_interaction.semantic_map_service.rooms_on_floor",
        return_value=[room_a, room_b],
    ), patch(
        "app.services.world_interaction.semantic_map_service._intra_floor_edges",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service._agents_near",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service.resolve_ancestors",
        return_value=(floor, building, world),
    ):
        payload = build_floor_focus_map(session, location, floor)

    assert payload["viewLayer"] == "floor"
    assert payload["layout"] == "grid"
    assert payload["floorPlanReady"] is True
    assert len(payload["nodes"]) == 2


def test_build_floor_focus_map_list_fallback_without_grid():
    location = _room_node(1, name="Current")
    floor = SimpleNamespace(id=10, type_code="building_floor", name="3F", location_id=20, attributes={"display_name": "3F"}, tags=[])
    room_a = _room_node(2, name="Lab", grid=False)

    session = MagicMock()
    with patch(
        "app.services.world_interaction.semantic_map_service.rooms_on_floor",
        return_value=[room_a],
    ), patch(
        "app.services.world_interaction.semantic_map_service._intra_floor_edges",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service._agents_near",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service.resolve_ancestors",
        return_value=(floor, None, None),
    ):
        payload = build_floor_focus_map(session, location, floor)

    assert payload["layout"] == "list"
    assert payload["floorPlanReady"] is False
    assert payload["nodes"] == []
    assert len(payload["floorRoomList"]) == 1
    assert payload["floorRoomList"][0]["name"] == "Lab"


def test_build_building_focus_map_lists_floors():
    location = _room_node(1, name="Current")
    building = SimpleNamespace(id=20, type_code="building", name="F3", location_id=30, attributes={"display_name": "F3 Tower"}, tags=[])
    floor_a = SimpleNamespace(id=11, type_code="building_floor", name="1F", location_id=20, attributes={"display_name": "1F", "floor_number": 1}, tags=[])
    floor_b = SimpleNamespace(id=12, type_code="building_floor", name="2F", location_id=20, attributes={"display_name": "2F", "floor_number": 2}, tags=[])

    session = MagicMock()
    with patch(
        "app.services.world_interaction.semantic_map_service.floors_in_building",
        return_value=[floor_a, floor_b],
    ), patch(
        "app.services.world_interaction.semantic_map_service.resolve_ancestors",
        return_value=(floor_a, building, None),
    ):
        payload = build_building_focus_map(session, location, building)

    assert payload["viewLayer"] == "building"
    assert payload["layout"] == "hierarchy"
    assert len(payload["nodes"]) == 2
    assert payload["nodes"][0]["type"] == "floor"


def test_build_focus_map_drill_floor_does_not_change_location_id():
    location = _room_node(1, name="Current")
    floor = SimpleNamespace(id=10, type_code="building_floor", name="3F", location_id=20, attributes={"display_name": "3F"}, tags=[])

    session = MagicMock()
    with patch(
        "app.services.world_interaction.semantic_map_service.resolve_ancestors",
        return_value=(floor, None, None),
    ), patch(
        "app.services.world_interaction.semantic_map_service.resolve_anchor_node",
        return_value=floor,
    ), patch(
        "app.services.world_interaction.semantic_map_service.build_floor_focus_map",
        return_value={"viewLayer": "floor", "currentSpaceId": "1", "nodes": [], "edges": [], "mode": "focus"},
    ) as floor_builder:
        payload = build_focus_map(session, location, view_layer="floor", anchor_id="10")

    floor_builder.assert_called_once()
    assert payload["viewLayer"] == "floor"
    assert payload["currentSpaceId"] == "1"


def test_build_campus_focus_map_uses_campus_grid_coordinates():
    location = _room_node(1, name="Current")
    world = SimpleNamespace(
        id=30,
        type_code="world",
        name="HiCampus",
        attributes={"world_id": "hicampus", "package_node_id": "hicampus_world"},
        tags=[],
    )
    building = SimpleNamespace(
        id=20,
        type_code="building",
        name="F3",
        attributes={
            "display_name": "F3 Training Center",
            "package_node_id": "hicampus_f3",
            "world_id": "hicampus",
            "campus_grid_col": 22,
            "campus_grid_row": 8,
        },
        tags=[],
    )

    session = MagicMock()
    with patch(
        "app.services.world_interaction.semantic_map_service.buildings_in_world",
        return_value=[building],
    ), patch(
        "app.services.world_interaction.semantic_map_service.outdoor_landmark_rooms",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service.resolve_ancestors",
        return_value=(None, building, world),
    ):
        payload = build_campus_focus_map(session, location, world)

    assert payload["viewLayer"] == "campus"
    assert payload["layout"] == "grid"
    node = payload["nodes"][0]
    assert node["x"] == 10 + 22 * 12
    assert node["y"] == 10 + 8 * 12


def test_build_campus_layer_clusters_when_over_limit():
    location = _room_node(1, name="Current")
    world = SimpleNamespace(
        id=30,
        type_code="world",
        name="HiCampus",
        attributes={"world_id": "hicampus"},
        tags=[],
    )
    buildings = []
    for index in range(5):
        buildings.append(
            SimpleNamespace(
                id=100 + index,
                type_code="building",
                name=f"B{index}",
                attributes={"display_name": f"B{index}", "package_node_id": f"b{index}", "world_id": "hicampus"},
                tags=[],
            )
        )

    session = MagicMock()
    from app.services.world_interaction.types import DISPLAY_POLICY

    policy = dict(DISPLAY_POLICY)
    policy["maxCampusNodesVisible"] = 3
    with patch(
        "app.services.world_interaction.semantic_map_service.DISPLAY_POLICY",
        policy,
    ), patch(
        "app.services.world_interaction.semantic_map_service.buildings_in_world",
        return_value=buildings,
    ), patch(
        "app.services.world_interaction.semantic_map_service.outdoor_landmark_rooms",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service.resolve_ancestors",
        return_value=(None, None, world),
    ):
        payload = build_campus_focus_map(session, location, world)

    assert any(node["type"] == "cluster" for node in payload["nodes"])


def test_build_floor_focus_map_clusters_overflow_rooms():
    location = _room_node(1, name="Current")
    floor = SimpleNamespace(
        id=10,
        type_code="building_floor",
        name="3F",
        location_id=20,
        attributes={"display_name": "3F", "package_node_id": "pkg-floor"},
        tags=[],
    )
    rooms = [_room_node(room_id, name=f"R{room_id}", grid=True) for room_id in range(2, 30)]

    session = MagicMock()
    from app.services.world_interaction.types import DISPLAY_POLICY

    policy = dict(DISPLAY_POLICY)
    policy["maxFloorNodesVisible"] = 5
    with patch(
        "app.services.world_interaction.semantic_map_service.DISPLAY_POLICY",
        policy,
    ), patch(
        "app.services.world_interaction.semantic_map_service.rooms_on_floor",
        return_value=rooms,
    ), patch(
        "app.services.world_interaction.semantic_map_service._intra_floor_edges",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service._agents_near",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service.resolve_ancestors",
        return_value=(floor, None, None),
    ):
        payload = build_floor_focus_map(session, location, floor)

    cluster_nodes = [node for node in payload["nodes"] if node["type"] == "cluster"]
    assert len(cluster_nodes) == 1
    assert cluster_nodes[0]["overflowCount"] > 0
    assert cluster_nodes[0]["drillAnchorId"]


def test_build_campus_focus_map_includes_outdoor_spine_edges():
    location = _room_node(1, name="Current")
    world = SimpleNamespace(
        id=30,
        type_code="world",
        name="HiCampus",
        attributes={"world_id": "hicampus"},
        tags=[],
    )
    gate = SimpleNamespace(
        id=201,
        type_code="room",
        name="Gate",
        attributes={"display_name": "Gate", "package_node_id": "hicampus_gate", "world_id": "hicampus"},
        tags=[],
    )
    bridge = SimpleNamespace(
        id=202,
        type_code="room",
        name="Bridge",
        attributes={"display_name": "Bridge", "package_node_id": "hicampus_bridge", "world_id": "hicampus"},
        tags=["environment:outdoor"],
    )
    rel = SimpleNamespace(id=9001, source_id=201, target_id=202, attributes={"direction": "east"}, target_role=None)

    session = MagicMock()
    with patch(
        "app.services.world_interaction.semantic_map_service.buildings_in_world",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service.outdoor_landmark_rooms",
        return_value=[gate, bridge],
    ), patch(
        "app.services.world_interaction.semantic_map_service.outdoor_landmark_edges",
        return_value=[rel],
    ), patch(
        "app.services.world_interaction.semantic_map_service.resolve_ancestors",
        return_value=(None, None, world),
    ):
        payload = build_campus_focus_map(session, location, world)

    assert len(payload["edges"]) == 1
    assert payload["edges"][0]["from"] == "201"
    assert payload["edges"][0]["to"] == "202"


def test_apply_event_space_ids_highlights_related_spaces():
    focus_map = {
        "mode": "focus",
        "currentSpaceId": "1",
        "nodes": [
            {"id": "1", "status": "current", "activeEventIds": []},
            {"id": "2", "status": "visible", "activeEventIds": []},
            {"id": "3", "status": "visible", "activeEventIds": []},
        ],
        "edges": [],
    }
    updated = apply_event_space_ids(focus_map, ["2"])
    assert updated["mode"] == "event"
    assert next(n for n in updated["nodes"] if n["id"] == "2")["status"] == "active"
    assert next(n for n in updated["nodes"] if n["id"] == "3")["status"] == "visible"


def test_build_map_query_patch_building_search_switches_to_campus():
    session = MagicMock()
    building = SimpleNamespace(id=20, type_code="building", location_id=30, attributes={}, tags=[])
    with patch(
        "app.services.world_interaction.semantic_map_service.get_active_node",
        return_value=building,
    ):
        map_patch = build_map_query_patch(
            session,
            [{"entity_id": "20", "entity_type": "space", "title": "F3 Training Center"}],
            "F3",
        )
    assert map_patch["viewLayer"] == "campus"
    assert map_patch["highlightedNodeIds"] == ["20"]
