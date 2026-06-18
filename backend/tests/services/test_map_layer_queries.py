"""Unit tests for semantic map layer graph queries."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.world_interaction.map_layer_queries import (
    _circulation_hub_rooms_by_building,
    _default_floor_map_anchor,
    floor_map_look_exits,
    rooms_for_floor_map,
)


def _room(
    room_id: int,
    *,
    package_node_id: str,
    tags: list[str] | None = None,
    room_type: str = "normal",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=room_id,
        type_code="room",
        name=package_node_id,
        tags=tags or [],
        attributes={
            "package_node_id": package_node_id,
            "world_id": "demo_world",
            "room_type": room_type,
            "map_grid_col": room_id,
            "map_grid_row": 1,
            "map_grid_span_w": 1,
            "map_grid_span_h": 1,
        },
    )


def test_rooms_for_floor_map_excludes_unreachable_multi_hop_neighbors():
    floor = SimpleNamespace(id=10, type_code="building_floor", attributes={"package_node_id": "b1_01f"})
    circulation = _room(101, package_node_id="b1_01f_circulation", tags=["space:circulation"], room_type="circulation")
    plaza = _room(102, package_node_id="campus_plaza", room_type="plaza")
    bridge = _room(103, package_node_id="campus_bridge", room_type="circulation")
    restroom = _room(104, package_node_id="b1_01f_restroom")
    electrical = _room(105, package_node_id="b1_01f_electrical", room_type="special")
    gate = _room(106, package_node_id="campus_gate", room_type="landmark", tags=["layer:entry"])
    floor_rooms = [circulation, plaza, bridge, restroom, electrical, gate]

    def mock_exits(session, room_id: int):
        exits = {
            101: [{"target_id": 102}, {"target_id": 104}, {"target_id": 105}],
            102: [{"target_id": 103}, {"target_id": 101}],
            103: [{"target_id": 106}, {"target_id": 102}],
            104: [{"target_id": 101}],
            105: [{"target_id": 101}],
            106: [{"target_id": 103}],
        }
        return exits.get(int(room_id), [])

    session = MagicMock()

    with patch(
        "app.services.world_interaction.map_layer_queries.rooms_on_floor",
        return_value=floor_rooms,
    ), patch(
        "app.services.world_interaction.map_layer_queries.connects_to_exits_from_room",
        side_effect=mock_exits,
    ):
        visible = rooms_for_floor_map(session, floor, circulation)

    visible_ids = {int(room.id) for room in visible}
    assert visible_ids == {101, 102, 104, 105}
    assert 103 not in visible_ids
    assert 106 not in visible_ids


def test_rooms_for_floor_map_one_hop_from_plaza_includes_bridge_not_gate():
    floor = SimpleNamespace(id=10, type_code="building_floor", attributes={"package_node_id": "b1_01f"})
    circulation = _room(101, package_node_id="b1_01f_circulation", tags=["space:circulation"], room_type="circulation")
    plaza = _room(102, package_node_id="campus_plaza", room_type="plaza")
    bridge = _room(103, package_node_id="campus_bridge", room_type="circulation")
    gate = _room(106, package_node_id="campus_gate", room_type="landmark", tags=["layer:entry"])
    floor_rooms = [circulation, plaza, bridge, gate]

    def mock_exits(session, room_id: int):
        exits = {
            102: [{"target_id": 103}, {"target_id": 101}],
            103: [{"target_id": 106}, {"target_id": 102}],
            101: [{"target_id": 102}],
            106: [{"target_id": 103}],
        }
        return exits.get(int(room_id), [])

    session = MagicMock()

    with patch(
        "app.services.world_interaction.map_layer_queries.rooms_on_floor",
        return_value=floor_rooms,
    ), patch(
        "app.services.world_interaction.map_layer_queries.connects_to_exits_from_room",
        side_effect=mock_exits,
    ):
        visible = rooms_for_floor_map(session, floor, plaza)

    visible_ids = {int(room.id) for room in visible}
    assert visible_ids == {102, 103, 101}
    assert 106 not in visible_ids


def test_rooms_for_floor_map_includes_gate_when_anchor_is_gate():
    floor = SimpleNamespace(id=10, type_code="building_floor", attributes={"package_node_id": "b1_01f"})
    circulation = _room(101, package_node_id="b1_01f_circulation", tags=["space:circulation"], room_type="circulation")
    bridge = _room(103, package_node_id="campus_bridge", room_type="circulation")
    gate = _room(106, package_node_id="campus_gate", room_type="landmark", tags=["layer:entry"])
    floor_rooms = [circulation, bridge, gate]

    def mock_exits(session, room_id: int):
        exits = {
            106: [{"target_id": 103}],
            103: [{"target_id": 106}, {"target_id": 101}],
            101: [{"target_id": 103}],
        }
        return exits.get(int(room_id), [])

    session = MagicMock()

    with patch(
        "app.services.world_interaction.map_layer_queries.rooms_on_floor",
        return_value=floor_rooms,
    ), patch(
        "app.services.world_interaction.map_layer_queries.connects_to_exits_from_room",
        side_effect=mock_exits,
    ):
        visible = rooms_for_floor_map(session, floor, gate)

    visible_ids = {int(room.id) for room in visible}
    assert 106 in visible_ids
    assert 103 in visible_ids


def test_rooms_for_floor_map_uses_circulation_hub_when_anchor_not_on_floor():
    floor = SimpleNamespace(id=10, type_code="building_floor", attributes={"package_node_id": "b1_01f"})
    circulation = _room(101, package_node_id="b1_01f_circulation", tags=["space:circulation"], room_type="circulation")
    plaza = _room(102, package_node_id="campus_plaza", room_type="plaza")
    gate = _room(106, package_node_id="campus_gate", room_type="landmark", tags=["layer:entry"])
    off_floor_location = _room(999, package_node_id="other_room")
    floor_rooms = [circulation, plaza, gate]

    def mock_exits(session, room_id: int):
        exits = {
            101: [{"target_id": 102}],
            102: [{"target_id": 101}],
        }
        return exits.get(int(room_id), [])

    session = MagicMock()

    with patch(
        "app.services.world_interaction.map_layer_queries.rooms_on_floor",
        return_value=floor_rooms,
    ), patch(
        "app.services.world_interaction.map_layer_queries.connects_to_exits_from_room",
        side_effect=mock_exits,
    ):
        visible = rooms_for_floor_map(session, floor, off_floor_location)

    visible_ids = {int(room.id) for room in visible}
    assert visible_ids == {101, 102}
    assert 106 not in visible_ids


def test_floor_map_look_exits_skips_vertical_only():
    circulation = _room(101, package_node_id="b1_f1_circulation", tags=["space:circulation"], room_type="circulation")
    plaza = _room(102, package_node_id="campus_plaza", room_type="plaza")
    upstairs = _room(201, package_node_id="b1_f2_circulation", tags=["space:circulation"], room_type="circulation")

    def mock_exits(session, room_id: int):
        return [
            {"direction": "south", "target_id": 102},
            {"direction": "up", "target_id": 201},
        ]

    session = MagicMock()
    with patch(
        "app.services.world_interaction.map_layer_queries.connects_to_exits_from_room",
        side_effect=mock_exits,
    ):
        rows = floor_map_look_exits(session, circulation)

    assert len(rows) == 1
    assert int(rows[0]["target_id"]) == 102


def test_rooms_for_floor_map_upper_floor_uses_same_look_rules():
    """Non-F1 floors use the same anchor + 1-hop rules (no building-specific hardcoding)."""
    floor_5f = SimpleNamespace(id=50, type_code="building_floor", attributes={"package_node_id": "b1_05f", "floor_number": 5})
    circulation = _room(501, package_node_id="b1_05f_circulation", tags=["space:circulation"], room_type="circulation")
    meeting = _room(502, package_node_id="b1_05f_meeting", room_type="meeting")
    floor_rooms = [circulation, meeting]

    def mock_exits(session, room_id: int):
        if int(room_id) == 501:
            return [{"direction": "north", "target_id": 502}]
        return []

    session = MagicMock()
    with patch(
        "app.services.world_interaction.map_layer_queries.rooms_on_floor",
        return_value=floor_rooms,
    ), patch(
        "app.services.world_interaction.map_layer_queries.connects_to_exits_from_room",
        side_effect=mock_exits,
    ):
        visible = rooms_for_floor_map(session, floor_5f, circulation)

    assert {int(r.id) for r in visible} == {501, 502}


def test_circulation_hub_rooms_by_building_uses_tags_not_package_suffix():
    building_a = SimpleNamespace(
        id=20,
        type_code="building",
        attributes={"package_node_id": "tower_a", "world_id": "demo_world"},
        tags=[],
    )
    first_floor = SimpleNamespace(
        id=11,
        type_code="building_floor",
        attributes={"package_node_id": "tower_a_01f", "floor_number": 1},
        tags=[],
    )
    hub = _room(101, package_node_id="custom_corridor_hub", tags=["space:circulation"], room_type="circulation")
    session = MagicMock()

    with patch(
        "app.services.world_interaction.map_layer_queries.floors_in_building",
        return_value=[first_floor],
    ), patch(
        "app.services.world_interaction.map_layer_queries.rooms_on_floor",
        return_value=[hub],
    ):
        hub_ids, room_to_building = _circulation_hub_rooms_by_building(
            session,
            world_id="demo_world",
            building_nodes=[building_a],
        )

    assert hub_ids == {101}
    assert room_to_building[101] == "tower_a"


def test_default_floor_map_anchor_skips_outdoor_connector_circulation():
    bridge = _room(
        92,
        package_node_id="world_bridge",
        room_type="circulation",
        tags=["environment:outdoor", "space:core", "layer:connector"],
    )
    circulation = _room(
        93,
        package_node_id="tower_a_01f_circulation_01",
        tags=["space:circulation"],
        room_type="circulation",
    )
    hub = _default_floor_map_anchor([bridge, circulation])
    assert hub is not None
    assert int(hub.id) == 93


def test_circulation_hub_rooms_by_building_skips_outdoor_connector_on_first_floor():
    building_a = SimpleNamespace(
        id=20,
        type_code="building",
        attributes={"package_node_id": "tower_a", "world_id": "demo_world"},
        tags=[],
    )
    first_floor = SimpleNamespace(
        id=11,
        type_code="building_floor",
        attributes={"package_node_id": "tower_a_01f", "floor_number": 1},
        tags=[],
    )
    bridge = _room(
        92,
        package_node_id="world_bridge",
        room_type="circulation",
        tags=["environment:outdoor", "space:core", "layer:connector"],
    )
    circulation = _room(
        93,
        package_node_id="tower_a_01f_circulation_01",
        tags=["space:circulation"],
        room_type="circulation",
    )
    session = MagicMock()

    with patch(
        "app.services.world_interaction.map_layer_queries.floors_in_building",
        return_value=[first_floor],
    ), patch(
        "app.services.world_interaction.map_layer_queries.rooms_on_floor",
        return_value=[bridge, circulation],
    ):
        hub_ids, room_to_building = _circulation_hub_rooms_by_building(
            session,
            world_id="demo_world",
            building_nodes=[building_a],
        )

    assert hub_ids == {93}
    assert room_to_building[93] == "tower_a"
