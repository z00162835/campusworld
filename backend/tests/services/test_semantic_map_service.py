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
    build_world_focus_map,
)
from app.services.world_interaction.types import DISPLAY_POLICY


def test_logical_zone_occupant_does_not_overlap_compass_north():
    from app.services.world_interaction.map_layout import logical_zone_positions

    north_exit = compass_position("north")
    occ_pos = logical_zone_positions(1, "occupant")[0]
    assert occ_pos != north_exit
    assert occ_pos[1] > north_exit[1]


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
        "app.services.world_interaction.semantic_map_service.room_contents",
        return_value=([], [], []),
    ), patch(
        "app.services.world_interaction.semantic_map_service.hub_root_node",
        return_value=None,
    ), patch(
        "app.services.world_interaction.semantic_map_service.connects_to_exits_from_room",
        return_value=[
            {
                "direction": "north",
                "target_id": 2,
                "target_display_name": "North Room",
                "target_short_desc": "Ahead",
            }
        ],
    ), patch(
        "app.services.world_interaction.semantic_map_service.get_active_node",
        return_value=target,
    ), patch(
        "app.services.world_interaction.semantic_map_service.resolve_ancestors",
        return_value=(None, None, None),
    ):
        payload = build_room_focus_map(session, location)

    assert payload["viewLayer"] == "room"
    assert payload["layout"] == "logical"
    assert payload["orientation"] == "north-up"
    assert len(payload["nodes"]) == 2
    assert payload["nodes"][0]["status"] == "current"
    north_node = next(n for n in payload["nodes"] if n["id"] == "2")
    assert north_node["logicalZone"] == "exit"
    assert north_node["y"] < 50
    assert north_node["y"] == 22
    assert payload["edges"][0]["direction"] == "north"
    assert payload["neighborLinks"][0]["direction"] == "north"
    assert payload["neighborLinks"][0]["targetId"] == "2"
    assert "command" not in payload["neighborLinks"][0]


def test_build_room_focus_map_plaza_exit_to_indoor_shows_building():
    plaza = SimpleNamespace(
        id=301,
        type_code="room",
        name="HiCampus 广场",
        location_id=41,
        attributes={
            "display_name": "HiCampus 广场",
            "package_node_id": "hicampus_plaza",
            "world_id": "hicampus",
            "building_id": "hicampus_f1",
        },
        tags=["environment:outdoor", "plaza"],
    )
    bridge = SimpleNamespace(
        id=302,
        type_code="room",
        name="HiCampus 长桥",
        attributes={
            "display_name": "HiCampus 长桥",
            "package_node_id": "hicampus_bridge",
            "world_id": "hicampus",
            "room_type": "circulation",
        },
        tags=["environment:outdoor", "layer:connector"],
    )
    circulation = SimpleNamespace(
        id=303,
        type_code="room",
        name="F1 交通核",
        location_id=41,
        attributes={
            "display_name": "F1 交通核",
            "package_node_id": "hicampus_f1_01f_circulation_01",
            "world_id": "hicampus",
            "building_id": "hicampus_f1",
            "room_type": "circulation",
        },
        tags=["space:circulation"],
    )
    f1_floor = SimpleNamespace(
        id=41,
        type_code="building_floor",
        name="01F",
        location_id=20,
        attributes={"display_name": "F1 · 1F", "building_id": "hicampus_f1", "world_id": "hicampus"},
        tags=[],
    )
    f1_building = SimpleNamespace(
        id=20,
        type_code="building",
        name="F1 Office Tower",
        location_id=30,
        attributes={
            "display_name": "F1 Office Tower",
            "package_node_id": "hicampus_f1",
            "world_id": "hicampus",
        },
        tags=[],
    )
    world = SimpleNamespace(
        id=30,
        type_code="world",
        name="HiCampus",
        attributes={"display_name": "HiCampus", "world_id": "hicampus"},
        tags=[],
    )

    session = MagicMock()
    targets = {302: bridge, 303: circulation, 20: f1_building}

    def get_node(_s, nid):
        return targets.get(int(nid))

    def resolve_side_effect(_s, room):
        if int(room.id) == 301:
            return f1_floor, f1_building, world
        if int(room.id) == 303:
            return f1_floor, f1_building, world
        return None, None, world

    with patch(
        "app.services.world_interaction.semantic_map_service.room_contents",
        return_value=([], [], []),
    ), patch(
        "app.services.world_interaction.semantic_map_service.hub_root_node",
        return_value=None,
    ), patch(
        "app.services.world_interaction.semantic_map_service.connects_to_exits_from_room",
        return_value=[
            {
                "direction": "north",
                "target_id": 303,
                "target_display_name": "F1 交通核",
            },
            {
                "direction": "south",
                "target_id": 302,
                "target_display_name": "HiCampus 长桥",
            },
        ],
    ), patch(
        "app.services.world_interaction.semantic_map_service.get_active_node",
        side_effect=get_node,
    ), patch(
        "app.services.world_interaction.semantic_map_service.resolve_ancestors",
        side_effect=resolve_side_effect,
    ), patch(
        "app.services.world_interaction.semantic_map_service.building_for_floor",
        return_value=f1_building,
    ):
        payload = build_room_focus_map(session, plaza)

    exit_nodes = [n for n in payload["nodes"] if n.get("logicalZone") == "exit"]
    assert len(exit_nodes) == 2
    north = next(n for n in exit_nodes if n.get("direction") == "north")
    south = next(n for n in exit_nodes if n.get("direction") == "south")
    assert north["type"] == "building"
    assert north["id"] == "20"
    assert north["name"] == "F1 Office Tower"
    assert north["crossBuilding"] is True
    assert north["drillAnchorId"] == "303"
    assert south["type"] == "bridge"
    assert south["id"] == "302"
    assert south.get("crossBuilding") is not True
    north_pos = (north["x"], north["y"])
    occupant_groups = [n for n in payload["nodes"] if n.get("id", "").startswith("cluster:room:") and n.get("logicalZone") == "occupant"]
    assert len(occupant_groups) == 0


def test_build_room_focus_map_groups_content_with_single_edges():
    location = SimpleNamespace(
        id=1,
        type_code="room",
        name="Lab",
        location_id=10,
        attributes={"display_name": "Lab"},
        tags=[],
    )
    agent = SimpleNamespace(id=11, type_code="account", name="admin", attributes={"display_name": "admin"}, tags=[], trait_class="AGENT")
    device_a = SimpleNamespace(id=21, type_code="lighting_fixture", name="Light", attributes={"display_name": "Light"}, tags=[], trait_class="DEVICE")
    device_b = SimpleNamespace(id=22, type_code="network_access_point", name="AP", attributes={"display_name": "AP"}, tags=[], trait_class="DEVICE")
    item = SimpleNamespace(id=31, type_code="lounge_furniture", name="Bench", attributes={"display_name": "Bench"}, tags=[], trait_class="ITEM")

    session = MagicMock()
    with patch(
        "app.services.world_interaction.semantic_map_service.room_contents",
        return_value=([agent], [device_a, device_b], [item]),
    ), patch(
        "app.services.world_interaction.semantic_map_service.hub_root_node",
        return_value=None,
    ), patch(
        "app.services.world_interaction.semantic_map_service.connects_to_exits_from_room",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service.resolve_ancestors",
        return_value=(None, None, None),
    ), patch(
        "app.services.world_interaction.semantic_map_service._agents_near",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service._neighbor_links",
        return_value=[],
    ):
        payload = build_room_focus_map(session, location)

    group_nodes = [n for n in payload["nodes"] if str(n.get("id", "")).startswith("cluster:room:")]
    assert len(group_nodes) == 2
    assert {n["logicalZone"] for n in group_nodes} == {"device", "item"}
    group_edges = [e for e in payload["edges"] if str(e.get("id", "")).startswith("logical_group_")]
    assert len(group_edges) == 0
    device_group = next(n for n in group_nodes if n["logicalZone"] == "device")
    assert device_group["objectIds"] == ["21", "22"]
    assert device_group["type"] == "cluster"
    assert device_group["groupMembers"] == [
        {"id": "21", "name": "Light", "type": "device", "status": "visible"},
        {"id": "22", "name": "AP", "type": "device", "status": "visible"},
    ]
    item_group = next(n for n in group_nodes if n["logicalZone"] == "item")
    assert item_group["groupMembers"] == [
        {"id": "31", "name": "Bench", "type": "object", "status": "visible"},
    ]
    assert payload["roomOccupants"] == [
        {"id": "11", "name": "admin", "type": "agent", "status": "visible"},
    ]


def test_build_room_focus_map_same_building_exit_shows_room():
    location = SimpleNamespace(
        id=1,
        type_code="room",
        name="Office",
        location_id=10,
        attributes={"display_name": "Office", "building_id": "hicampus_f1", "world_id": "hicampus"},
        tags=[],
    )
    neighbor = SimpleNamespace(
        id=2,
        type_code="room",
        name="Meeting",
        location_id=10,
        attributes={"display_name": "Meeting Room", "building_id": "hicampus_f1", "world_id": "hicampus"},
        tags=[],
    )
    floor = SimpleNamespace(
        id=10,
        type_code="building_floor",
        name="02F",
        location_id=20,
        attributes={"building_id": "hicampus_f1", "world_id": "hicampus"},
        tags=[],
    )
    building = SimpleNamespace(
        id=20,
        type_code="building",
        name="F1 Office Tower",
        location_id=30,
        attributes={"display_name": "F1 Office Tower", "package_node_id": "hicampus_f1"},
        tags=[],
    )

    session = MagicMock()

    with patch(
        "app.services.world_interaction.semantic_map_service.room_contents",
        return_value=([], [], []),
    ), patch(
        "app.services.world_interaction.semantic_map_service.hub_root_node",
        return_value=None,
    ), patch(
        "app.services.world_interaction.semantic_map_service.connects_to_exits_from_room",
        return_value=[
            {
                "direction": "east",
                "target_id": 2,
                "target_display_name": "Meeting Room",
            },
        ],
    ), patch(
        "app.services.world_interaction.semantic_map_service.get_active_node",
        return_value=neighbor,
    ), patch(
        "app.services.world_interaction.semantic_map_service.resolve_ancestors",
        return_value=(floor, building, None),
    ):
        payload = build_room_focus_map(session, location)

    exit_node = next(n for n in payload["nodes"] if n.get("logicalZone") == "exit")
    assert exit_node["type"] == "room"
    assert exit_node["id"] == "2"
    assert exit_node["name"] == "Meeting Room"
    assert exit_node.get("crossBuilding") is not True


def test_build_room_focus_map_preserves_exits_when_optional_nodes_exceed_cap():
    location = SimpleNamespace(
        id=1,
        type_code="room",
        name="Plaza",
        location_id=10,
        attributes={
            "display_name": "Plaza",
            "package_node_id": "hicampus_plaza",
            "world_id": "hicampus",
        },
        tags=["environment:outdoor", "plaza"],
    )
    bridge = SimpleNamespace(
        id=302,
        type_code="room",
        name="Bridge",
        attributes={"display_name": "Bridge", "package_node_id": "hicampus_bridge", "room_type": "circulation"},
        tags=["environment:outdoor", "layer:connector"],
    )
    circulation = SimpleNamespace(
        id=303,
        type_code="room",
        name="Circulation",
        location_id=10,
        attributes={
            "display_name": "Circulation",
            "package_node_id": "hicampus_f1_01f_circulation_01",
            "building_id": "hicampus_f1",
            "room_type": "circulation",
        },
        tags=["space:circulation"],
    )
    building = SimpleNamespace(
        id=20,
        type_code="building",
        name="F1 Tower",
        attributes={"display_name": "F1 Tower", "package_node_id": "hicampus_f1"},
        tags=[],
    )
    floor = SimpleNamespace(
        id=10,
        type_code="building_floor",
        name="01F",
        location_id=20,
        attributes={"building_id": "hicampus_f1"},
        tags=[],
    )
    filler_items = [
        SimpleNamespace(id=10 + i, type_code="lounge_furniture", name=f"Item {i}", attributes={"display_name": f"Item {i}"}, tags=[])
        for i in range(6)
    ]

    session = MagicMock()
    targets = {302: bridge, 303: circulation, 20: building}

    def get_node(_s, nid):
        return targets.get(int(nid))

    with patch(
        "app.services.world_interaction.semantic_map_service.room_contents",
        return_value=([], [], filler_items),
    ), patch(
        "app.services.world_interaction.semantic_map_service.hub_root_node",
        return_value=None,
    ), patch(
        "app.services.world_interaction.semantic_map_service.connects_to_exits_from_room",
        return_value=[
            {"direction": "north", "target_id": 303, "target_display_name": "Circulation"},
            {"direction": "south", "target_id": 302, "target_display_name": "Bridge"},
        ],
    ), patch(
        "app.services.world_interaction.semantic_map_service.get_active_node",
        side_effect=get_node,
    ), patch(
        "app.services.world_interaction.semantic_map_service.resolve_ancestors",
        side_effect=lambda _s, room: (
            (floor, building, None)
            if int(room.id) in {303}
            else (None, None, None)
        ),
    ), patch(
        "app.services.world_interaction.semantic_map_service.building_for_floor",
        return_value=building,
    ), patch(
        "app.services.world_interaction.semantic_map_service._agents_near",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service._neighbor_links",
        return_value=[],
    ):
        payload = build_room_focus_map(session, location)

    exit_nodes = [n for n in payload["nodes"] if n.get("logicalZone") == "exit"]
    assert len(exit_nodes) == 2
    assert any(n["type"] == "building" for n in exit_nodes)
    assert any(n["type"] == "bridge" for n in exit_nodes)
    item_group = next(
        (n for n in payload["nodes"] if n.get("id") == "cluster:room:1:item"),
        None,
    )
    assert item_group is not None
    assert item_group["objectIds"] == [str(10 + i) for i in range(6)]
    assert all(
        str(edge["to"]) in {n["id"] for n in payload["nodes"]}
        for edge in payload["edges"]
        if edge.get("direction")
    )


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
    floor = SimpleNamespace(id=10, type_code="building_floor", name="3F", location_id=20, attributes={"display_name": "3F", "package_node_id": "pkg-floor", "floor_number": 3}, tags=[])
    building = SimpleNamespace(id=20, type_code="building", name="F3", location_id=30, attributes={"display_name": "F3 Tower", "package_node_id": "pkg-b"}, tags=[])
    world = SimpleNamespace(id=30, type_code="world", name="HiCampus", location_id=None, attributes={"display_name": "HiCampus", "world_id": "hicampus"}, tags=[])
    floor_2f = SimpleNamespace(id=11, type_code="building_floor", name="2F", location_id=20, attributes={"display_name": "2F", "floor_number": 2}, tags=[])
    room_a = _room_node(2, name="Lab", grid=True)
    room_b = _room_node(3, name="Hall", grid=True)

    session = MagicMock()

    with patch(
        "app.services.world_interaction.semantic_map_service.rooms_for_floor_map",
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
    ), patch(
        "app.services.world_interaction.semantic_map_service.floors_in_building",
        return_value=[floor_2f, floor],
    ):
        payload = build_floor_focus_map(session, location, floor)

    assert payload["viewLayer"] == "floor"
    assert payload["layout"] == "grid"
    assert payload["floorPlanReady"] is True
    assert len(payload["nodes"]) == 2
    assert payload["nodes"][0]["mapGridCol"] == 4
    assert payload["floorGridBounds"]["minCol"] == 4
    assert len(payload["floorStack"]) == 2
    assert payload["floorStack"][-1]["status"] == "current"


def test_build_floor_focus_map_list_fallback_without_grid():
    location = _room_node(1, name="Current")
    floor = SimpleNamespace(id=10, type_code="building_floor", name="3F", location_id=20, attributes={"display_name": "3F"}, tags=[])
    room_a = _room_node(2, name="Lab", grid=False)

    session = MagicMock()
    with patch(
        "app.services.world_interaction.semantic_map_service.rooms_for_floor_map",
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


def test_build_focus_map_building_drill_skips_overview_to_floor():
    location = _room_node(1, name="Current")
    building = SimpleNamespace(
        id=20,
        type_code="building",
        name="F1",
        location_id=30,
        attributes={"display_name": "F1 Office Tower", "package_node_id": "hicampus_f1"},
        tags=[],
    )
    floor_1f = SimpleNamespace(
        id=11,
        type_code="building_floor",
        name="1F",
        location_id=20,
        attributes={"display_name": "F1 · 首层", "floor_number": 1},
        tags=[],
    )
    floor_2f = SimpleNamespace(
        id=12,
        type_code="building_floor",
        name="2F",
        location_id=20,
        attributes={"display_name": "F1 · 第2层", "floor_number": 2},
        tags=[],
    )

    session = MagicMock()
    with patch(
        "app.services.world_interaction.semantic_map_service.resolve_ancestors",
        return_value=(floor_2f, building, None),
    ), patch(
        "app.services.world_interaction.semantic_map_service.resolve_anchor_node",
        return_value=building,
    ), patch(
        "app.services.world_interaction.semantic_map_service.floors_in_building",
        return_value=[floor_1f, floor_2f],
    ), patch(
        "app.services.world_interaction.semantic_map_service.build_floor_focus_map",
        return_value={
            "viewLayer": "floor",
            "layout": "grid",
            "currentSpaceId": "1",
            "nodes": [],
            "edges": [],
            "mode": "focus",
        },
    ) as floor_builder, patch(
        "app.services.world_interaction.semantic_map_service.build_building_focus_map",
    ) as building_builder:
        payload = build_focus_map(session, location, view_layer="building", anchor_id="20")

    floor_builder.assert_called_once()
    call_floor = floor_builder.call_args[0][2]
    assert int(call_floor.id) == int(floor_1f.id)
    building_builder.assert_not_called()
    assert payload["viewLayer"] == "floor"
    assert payload["layout"] == "grid"


def test_build_floor_focus_map_breadcrumb_omits_building_layer():
    location = _room_node(1, name="Current")
    floor = SimpleNamespace(
        id=11,
        type_code="building_floor",
        name="1F",
        location_id=20,
        attributes={"display_name": "F1 · 首层", "floor_number": 1},
        tags=[],
    )
    building = SimpleNamespace(
        id=20,
        type_code="building",
        name="F1",
        location_id=30,
        attributes={"display_name": "F1 办公楼", "package_node_id": "hicampus_f1"},
        tags=[],
    )
    world = SimpleNamespace(
        id=30,
        type_code="world",
        name="HiCampus",
        attributes={"display_name": "HiCampus", "world_id": "hicampus"},
        tags=[],
    )
    hub = SimpleNamespace(id=1, type_code="room", name="hub", attributes={"display_name": "奇点屋", "room_name": "奇点屋"}, tags=[])

    session = MagicMock()
    with patch(
        "app.services.world_interaction.semantic_map_service.rooms_for_floor_map",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service._intra_floor_edges",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service._agents_near",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service.hub_root_node",
        return_value=hub,
    ), patch(
        "app.services.world_interaction.semantic_map_service.resolve_ancestors",
        return_value=(floor, building, world),
    ), patch(
        "app.services.world_interaction.semantic_map_service.floors_in_building",
        return_value=[floor],
    ):
        payload = build_floor_focus_map(session, location, floor, building=building, world=world)

    names = [c["name"] for c in payload["breadcrumb"]]
    assert names == ["奇点屋", "HiCampus", "F1 · 首层"]
    assert "F1 办公楼" not in names


def test_build_focus_map_building_drill_falls_back_when_no_floors():
    location = _room_node(1, name="Current")
    building = SimpleNamespace(
        id=20,
        type_code="building",
        name="Empty",
        location_id=30,
        attributes={"display_name": "Empty Tower"},
        tags=[],
    )

    session = MagicMock()
    with patch(
        "app.services.world_interaction.semantic_map_service.resolve_ancestors",
        return_value=(None, building, None),
    ), patch(
        "app.services.world_interaction.semantic_map_service.resolve_anchor_node",
        return_value=building,
    ), patch(
        "app.services.world_interaction.semantic_map_service._default_floor_for_building",
        return_value=None,
    ), patch(
        "app.services.world_interaction.semantic_map_service.build_building_focus_map",
        return_value={
            "viewLayer": "building",
            "layout": "hierarchy",
            "currentSpaceId": "1",
            "nodes": [],
            "edges": [],
            "mode": "focus",
        },
    ) as building_builder:
        payload = build_focus_map(session, location, view_layer="building", anchor_id="20")

    building_builder.assert_called_once()
    assert payload["viewLayer"] == "building"


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
    assert node["x"] == 88
    assert node["y"] == 88


def test_build_campus_focus_map_breadcrumb_uses_world_layer_not_player_building():
    hub = SimpleNamespace(
        id=1,
        type_code="room",
        name="奇点屋",
        attributes={"room_name": "奇点屋"},
        tags=[],
    )
    world = SimpleNamespace(
        id=30,
        type_code="world",
        name="HiCampus",
        attributes={"display_name": "HiCampus", "world_id": "hicampus"},
        tags=[],
    )
    plaza = SimpleNamespace(
        id=50,
        type_code="room",
        name="HiCampus 广场",
        location_id=41,
        attributes={
            "display_name": "HiCampus 广场",
            "package_node_id": "hicampus_plaza",
            "world_id": "hicampus",
        },
        tags=["environment:outdoor"],
    )
    building = SimpleNamespace(
        id=35,
        type_code="building",
        name="F1 Office Tower",
        location_id=None,
        attributes={"display_name": "F1 Office Tower", "world_id": "hicampus"},
        tags=[],
    )
    session = MagicMock()
    with patch(
        "app.services.world_interaction.semantic_map_service.buildings_in_world",
        return_value=[building],
    ), patch(
        "app.services.world_interaction.semantic_map_service.outdoor_landmark_rooms",
        return_value=[plaza],
    ), patch(
        "app.services.world_interaction.semantic_map_service.campus_inter_building_edges",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service.outdoor_landmark_edges",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service.hub_root_node",
        return_value=hub,
    ), patch(
        "app.services.world_interaction.semantic_map_service.get_active_node",
        return_value=plaza,
    ):
        payload = build_campus_focus_map(session, plaza, world, selected_entity_id="50")

    crumbs = payload["breadcrumb"]
    assert [c["name"] for c in crumbs] == ["奇点屋", "HiCampus", "HiCampus 广场"]
    assert [c["role"] for c in crumbs] == ["hub", "world", "campus_spot"]
    assert all(c.get("layer") != "building" for c in crumbs)


def test_build_campus_focus_map_breadcrumb_without_selected_spot():
    hub = SimpleNamespace(id=1, type_code="room", name="奇点屋", attributes={"room_name": "奇点屋"}, tags=[])
    world = SimpleNamespace(
        id=30,
        type_code="world",
        name="HiCampus",
        attributes={"display_name": "HiCampus", "world_id": "hicampus"},
        tags=[],
    )
    location = _room_node(1, name="Gate")
    session = MagicMock()
    with patch(
        "app.services.world_interaction.semantic_map_service.buildings_in_world",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service.outdoor_landmark_rooms",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service.campus_inter_building_edges",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service.outdoor_landmark_edges",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service.hub_root_node",
        return_value=hub,
    ):
        payload = build_campus_focus_map(session, location, world)

    assert [c["name"] for c in payload["breadcrumb"]] == ["奇点屋", "HiCampus"]


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
        "app.services.world_interaction.semantic_map_service.rooms_for_floor_map",
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
        "app.services.world_interaction.semantic_map_service.hub_root_node",
        return_value=None,
    ), patch(
        "app.services.world_interaction.semantic_map_service.campus_inter_building_edges",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service.resolve_ancestors",
        return_value=(None, None, world),
    ):
        payload = build_campus_focus_map(session, location, world)

    assert len(payload["edges"]) == 1
    assert payload["edges"][0]["from"] == "201"
    assert payload["edges"][0]["to"] == "202"


def test_room_building_id_ignores_outdoor_connectors_for_campus_edges():
    from app.services.world_interaction.map_layer_queries import _room_building_id

    plaza = SimpleNamespace(
        id=301,
        type_code="room",
        attributes={"package_node_id": "hicampus_plaza", "world_id": "hicampus"},
        tags=["environment:outdoor"],
    )
    circulation = SimpleNamespace(
        id=302,
        type_code="room",
        attributes={"package_node_id": "hicampus_f1_01f_circulation_01", "world_id": "hicampus"},
        tags=[],
    )
    f1_building = SimpleNamespace(
        id=20,
        type_code="building",
        attributes={"package_node_id": "hicampus_f1"},
        tags=[],
    )
    session = MagicMock()
    with patch(
        "app.services.world_interaction.map_layer_queries.resolve_ancestors",
        return_value=(None, f1_building, None),
    ):
        connector_ids = {301}
        assert _room_building_id(session, plaza, connector_ids=connector_ids) is None
        assert _room_building_id(session, circulation, connector_ids=connector_ids) == "hicampus_f1"


def test_campus_inter_building_edges_links_outdoor_plaza_to_f1_room():
    from app.models.graph import Node, Relationship
    from app.services.world_interaction.map_layer_queries import campus_inter_building_edges

    plaza = SimpleNamespace(
        id=301,
        type_code="room",
        attributes={"package_node_id": "hicampus_plaza", "world_id": "hicampus"},
        tags=["environment:outdoor"],
    )
    circulation = SimpleNamespace(
        id=302,
        type_code="room",
        attributes={"package_node_id": "hicampus_f1_01f_circulation_01", "world_id": "hicampus", "room_type": "circulation"},
        tags=["space:circulation"],
    )
    f1_building = SimpleNamespace(
        id=20,
        type_code="building",
        attributes={"package_node_id": "hicampus_f1", "world_id": "hicampus"},
        tags=[],
    )
    first_floor = SimpleNamespace(
        id=41,
        type_code="building_floor",
        attributes={"package_node_id": "hicampus_f1_01f", "floor_number": 1},
        tags=[],
    )
    rel = SimpleNamespace(id=9002, source_id=301, target_id=302, attributes={"direction": "north"})

    session = MagicMock()
    rel_query = MagicMock()
    rel_query.filter.return_value.all.return_value = [rel]
    node_query = MagicMock()
    node_rows = [plaza, circulation]
    filtered_node_query = MagicMock()
    filtered_node_query.filter.return_value = filtered_node_query
    filtered_node_query.order_by.return_value.all.return_value = node_rows
    filtered_node_query.all.return_value = node_rows
    node_query.filter.return_value = filtered_node_query

    def query_side_effect(model):
        if model is Relationship:
            return rel_query
        if model is Node:
            return node_query
        return MagicMock()

    session.query.side_effect = query_side_effect

    with patch(
        "app.services.world_interaction.map_layer_queries.resolve_ancestors",
        side_effect=lambda _s, room: (None, f1_building, None),
    ), patch(
        "app.services.world_interaction.map_layer_queries.floors_in_building",
        return_value=[first_floor],
    ), patch(
        "app.services.world_interaction.map_layer_queries.rooms_on_floor",
        return_value=[circulation],
    ):
        edges = campus_inter_building_edges(
            session,
            "hicampus",
            building_nodes=[f1_building],
            connector_nodes=[plaza],
        )

    assert len(edges) == 1
    assert edges[0].source_id == 301
    assert edges[0].target_id == 302


def test_outdoor_landmark_rooms_uses_semantic_tags_not_package_ids():
    from app.services.world_interaction.map_layer_queries import outdoor_landmark_rooms

    plaza = SimpleNamespace(
        id=301,
        type_code="room",
        attributes={
            "package_node_id": "world_plaza",
            "world_id": "demo_world",
            "campus_grid_col": 10,
            "campus_grid_row": 12,
        },
        tags=["environment:outdoor", "space:core", "plaza"],
    )
    bridge = SimpleNamespace(
        id=302,
        type_code="room",
        attributes={
            "package_node_id": "world_bridge",
            "world_id": "demo_world",
            "campus_grid_col": 14,
            "campus_grid_row": 16,
        },
        tags=["environment:outdoor", "space:core", "layer:connector"],
    )
    gate = SimpleNamespace(
        id=303,
        type_code="room",
        attributes={
            "package_node_id": "world_gate",
            "world_id": "demo_world",
            "campus_grid_col": 14,
            "campus_grid_row": 22,
        },
        tags=["space:core", "landmark", "layer:entry"],
    )
    indoor = SimpleNamespace(
        id=304,
        type_code="room",
        attributes={"package_node_id": "office_01", "world_id": "demo_world"},
        tags=["office"],
    )
    session = MagicMock()
    session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        plaza,
        bridge,
        gate,
        indoor,
    ]

    rooms = outdoor_landmark_rooms(session, "demo_world")

    assert {int(room.id) for room in rooms} == {301, 302, 303}


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


def test_build_world_focus_map_includes_hub_and_portals():
    location = SimpleNamespace(id=1, type_code="room", name="Gate", attributes={}, tags=[], location_id=None)
    hub = SimpleNamespace(
        id=99,
        type_code="room",
        name="Singularity",
        attributes={"is_root": True, "display_name": "Singularity Room"},
        tags=[],
    )
    world = SimpleNamespace(
        id=50,
        type_code="world",
        name="hicampus",
        attributes={"world_id": "hicampus", "display_name": "HiCampus"},
        tags=[],
    )
    entrance = SimpleNamespace(
        id=60,
        type_code="world_entrance",
        name="hicampus",
        attributes={"portal_world_id": "hicampus", "world_id": "hicampus"},
        tags=[],
    )
    session = MagicMock()
    with patch(
        "app.services.world_interaction.semantic_map_service.world_map_entries",
        return_value=(hub, [world], [entrance]),
    ), patch(
        "app.services.world_interaction.semantic_map_service.resolve_ancestors",
        return_value=(None, None, world),
    ):
        payload = build_world_focus_map(session, location)

    assert payload["viewLayer"] == "world"
    assert any(n["type"] == "hub" for n in payload["nodes"])
    assert any(n["type"] == "world" for n in payload["nodes"])
    assert any(e["label"] == "portal" for e in payload["edges"])


def test_build_focus_map_campus_drill_when_building_has_no_world_location():
    location = SimpleNamespace(
        id=96,
        type_code="room",
        name="Gate",
        location_id=41,
        attributes={"world_id": "hicampus", "package_node_id": "hicampus_gate"},
        tags=["environment:outdoor"],
    )
    world = SimpleNamespace(
        id=34,
        type_code="world",
        name="HiCampus",
        location_id=None,
        attributes={"world_id": "hicampus", "display_name": "HiCampus"},
        tags=[],
    )
    building = SimpleNamespace(
        id=35,
        type_code="building",
        name="F1",
        location_id=None,
        attributes={"world_id": "hicampus", "package_node_id": "hicampus_f1"},
        tags=[],
    )
    session = MagicMock()
    with patch(
        "app.services.world_interaction.semantic_map_service.get_active_node",
        side_effect=lambda _s, nid: {41: SimpleNamespace(id=41, type_code="building_floor", location_id=35), 34: world, 35: building}.get(int(nid)),
    ), patch(
        "app.services.world_interaction.semantic_map_service.hub_root_node",
        return_value=None,
    ), patch(
        "app.services.world_interaction.semantic_map_service.build_campus_focus_map",
        return_value={"viewLayer": "campus", "nodes": [{"id": "35", "type": "building"}], "edges": [], "mode": "focus"},
    ) as campus_mock:
        payload = build_focus_map(session, location, view_layer="campus", anchor_id="34")

    assert payload["viewLayer"] == "campus"
    campus_mock.assert_called_once()


def test_build_focus_map_room_drill_breadcrumb_uses_anchor_not_player_location():
    """Drilling into another building's room must not keep the player's building/floor in breadcrumb."""
    player_room = SimpleNamespace(
        id=1,
        type_code="room",
        name="F1 Hub",
        location_id=10,
        attributes={"display_name": "F1 Hub", "world_id": "hicampus"},
        tags=[],
    )
    f1_floor = SimpleNamespace(
        id=10,
        type_code="building_floor",
        name="hicampus_f1_01f",
        location_id=20,
        attributes={"display_name": "F1 · 1F", "floor_name": "1F", "world_id": "hicampus", "building_id": "hicampus_f1"},
        tags=[],
    )
    f1_building = SimpleNamespace(
        id=20,
        type_code="building",
        name="F1",
        location_id=30,
        attributes={"display_name": "F1 Office Tower", "package_node_id": "hicampus_f1", "world_id": "hicampus"},
        tags=[],
    )
    f6_room = SimpleNamespace(
        id=99,
        type_code="room",
        name="F6 Circulation",
        location_id=50,
        attributes={
            "display_name": "F6 公寓 · 第5层 交通核 1",
            "world_id": "hicampus",
            "floor_id": "hicampus_f6_05f",
        },
        tags=[],
    )
    f6_floor = SimpleNamespace(
        id=50,
        type_code="building_floor",
        name="hicampus_f6_05f",
        location_id=60,
        attributes={"display_name": "F6 · 5F", "floor_name": "第5层", "world_id": "hicampus", "building_id": "hicampus_f6"},
        tags=[],
    )
    f6_building = SimpleNamespace(
        id=60,
        type_code="building",
        name="F6",
        location_id=30,
        attributes={"display_name": "F6 公寓", "package_node_id": "hicampus_f6", "world_id": "hicampus"},
        tags=[],
    )
    world = SimpleNamespace(
        id=30,
        type_code="world",
        name="HiCampus",
        attributes={"display_name": "HiCampus", "world_id": "hicampus"},
        tags=[],
    )
    hub = SimpleNamespace(id=5, type_code="room", name="奇点屋", attributes={"room_name": "奇点屋"}, tags=[])

    session = MagicMock()

    def resolve_side_effect(_s, room):
        if int(room.id) == 99:
            return f6_floor, f6_building, world
        return f1_floor, f1_building, world

    with patch(
        "app.services.world_interaction.semantic_map_service.get_active_node",
        side_effect=lambda _s, nid: f6_room if int(nid) == 99 else None,
    ), patch(
        "app.services.world_interaction.semantic_map_service.resolve_ancestors",
        side_effect=resolve_side_effect,
    ), patch(
        "app.services.world_interaction.semantic_map_service.hub_root_node",
        return_value=hub,
    ), patch(
        "app.services.world_interaction.semantic_map_service.room_contents",
        return_value=([], [], []),
    ), patch(
        "app.services.world_interaction.semantic_map_service.connects_to_exits_from_room",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service._agents_near",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service._neighbor_links",
        return_value=[],
    ):
        payload = build_focus_map(session, player_room, view_layer="room", anchor_id="99")

    crumbs = payload["breadcrumb"]
    names = [c["name"] for c in crumbs]
    assert "F1 Office Tower" not in names
    assert "hicampus_f1_01f" not in names
    assert names[-1] == "F6 公寓 · 第5层 交通核 1"
    assert "F6 公寓" in names
    assert "F6 · 5F" in names


def test_build_floor_focus_map_adds_cross_building_look_exits():
    location = SimpleNamespace(
        id=101,
        type_code="room",
        name="Circulation",
        location_id=10,
        tags=["space:circulation"],
        attributes={
            "display_name": "Circulation",
            "package_node_id": "hicampus_f1_01f_circulation_01",
            "building_id": "hicampus_f1",
            "map_grid_col": 12,
            "map_grid_row": 8,
            "map_grid_span_w": 1,
            "map_grid_span_h": 1,
        },
    )
    plaza = SimpleNamespace(
        id=102,
        type_code="room",
        name="Plaza",
        location_id=10,
        tags=[],
        attributes={
            "display_name": "Plaza",
            "package_node_id": "hicampus_plaza",
            "building_id": "hicampus_f1",
            "map_grid_col": 12,
            "map_grid_row": 12,
            "map_grid_span_w": 1,
            "map_grid_span_h": 1,
            "room_type": "plaza",
        },
    )
    f3_circ = SimpleNamespace(
        id=301,
        type_code="room",
        name="F3 Circulation",
        tags=["space:circulation"],
        attributes={
            "package_node_id": "hicampus_f3_01f_circulation_01",
            "building_id": "hicampus_f3",
            "world_id": "hicampus",
            "room_type": "circulation",
        },
    )
    f3_building = SimpleNamespace(
        id=401,
        type_code="building",
        name="F3",
        attributes={"display_name": "F3 培训中心", "package_node_id": "hicampus_f3", "building_id": "hicampus_f3"},
        tags=[],
    )
    floor = SimpleNamespace(
        id=10,
        type_code="building_floor",
        name="1F",
        location_id=20,
        attributes={"display_name": "F1 · 首层", "package_node_id": "hicampus_f1_01f", "floor_number": 1},
        tags=[],
    )
    building = SimpleNamespace(
        id=20,
        type_code="building",
        name="F1",
        location_id=None,
        attributes={"display_name": "F1 办公楼", "package_node_id": "hicampus_f1", "world_id": "hicampus"},
        tags=[],
    )

    def mock_look_exits(session, anchor):
        _ = session, anchor
        return [
            {"direction": "south", "target_id": 102, "target_display_name": "HiCampus 广场"},
            {"direction": "northeast", "target_id": 301, "target_display_name": "F3 交通核"},
        ]

    rel_south = SimpleNamespace(id=9001, source_id=101, target_id=102, attributes={"direction": "south"})
    session = MagicMock()
    with patch(
        "app.services.world_interaction.semantic_map_service.rooms_for_floor_map",
        return_value=[location, plaza],
    ), patch(
        "app.services.world_interaction.semantic_map_service.rooms_on_floor",
        return_value=[location, plaza],
    ), patch(
        "app.services.world_interaction.semantic_map_service.floor_map_look_exits",
        side_effect=mock_look_exits,
    ), patch(
        "app.services.world_interaction.semantic_map_service.get_active_node",
        side_effect=lambda _session, node_id: {
            101: location,
            102: plaza,
            301: f3_circ,
            401: f3_building,
        }.get(int(node_id)),
    ), patch(
        "app.services.world_interaction.semantic_map_service.hub_root_node",
        return_value=None,
    ), patch(
        "app.services.world_interaction.semantic_map_service._same_building",
        side_effect=lambda _session, left, right: str((left.attributes or {}).get("building_id")) == str((right.attributes or {}).get("building_id")),
    ), patch(
        "app.services.world_interaction.semantic_map_service._building_for_room",
        return_value=f3_building,
    ), patch(
        "app.services.world_interaction.semantic_map_service._intra_floor_edges",
        return_value=[rel_south],
    ), patch(
        "app.services.world_interaction.semantic_map_service._agents_near",
        return_value=[],
    ), patch(
        "app.services.world_interaction.semantic_map_service.floors_in_building",
        return_value=[floor],
    ):
        payload = build_floor_focus_map(session, location, floor, building=building)

    node_ids = {node["id"] for node in payload["nodes"]}
    assert "102" in node_ids
    assert "401" in node_ids
    edge_directions = {edge.get("direction") for edge in payload["edges"]}
    assert "northeast" in edge_directions
    assert "south" in edge_directions
    assert "up" not in edge_directions
    cross_edges = [edge for edge in payload["edges"] if edge.get("crossBuilding")]
    assert len(cross_edges) == 1
    assert cross_edges[0]["to"] == "401"
