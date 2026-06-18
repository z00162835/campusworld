"""PostgreSQL integration tests for semantic map against seeded HiCampus graph."""

from __future__ import annotations

import pytest
from app.models.graph import Node
from app.services.world_interaction.map_layer_queries import get_active_node
from app.services.world_interaction.semantic_map_service import (
    apply_highlight_ids_to_focus_map,
    build_campus_focus_map,
    build_floor_focus_map,
    build_map_query_patch,
)


def _require_postgres():
    from app.core.database import engine

    if engine is None:
        pytest.skip("database engine not configured")
    if "postgresql" not in str(engine.url).lower():
        pytest.skip("PostgreSQL required for semantic map integration tests")


def _node_by_package_id(session, package_node_id: str) -> Node | None:
    return (
        session.query(Node)
        .filter(
            Node.is_active == True,
            Node.attributes["package_node_id"].astext == package_node_id,
        )
        .first()
    )


@pytest.mark.postgres_integration
def test_hicampus_campus_layer_has_outdoor_landmarks_and_spine_edges():
    _require_postgres()
    from app.core.database import SessionLocal

    session = SessionLocal()
    try:
        gate = _node_by_package_id(session, "hicampus_gate")
        bridge = _node_by_package_id(session, "hicampus_bridge")
        plaza = _node_by_package_id(session, "hicampus_plaza")
        world = _node_by_package_id(session, "hicampus_world")
        if not all([gate, bridge, plaza, world]):
            pytest.skip("HiCampus outdoor landmarks or world node not seeded; run world reload hicampus")

        focus_map = build_campus_focus_map(session, gate, world, mode="focus")
        node_ids = {node["id"] for node in focus_map.get("nodes") or []}
        assert str(gate.id) in node_ids
        assert str(bridge.id) in node_ids
        assert str(plaza.id) in node_ids
        assert len(focus_map.get("edges") or []) >= 10
        inter_building = [
            edge
            for edge in focus_map.get("edges") or []
            if edge.get("campusEdgeKind") == "inter-building"
        ]
        assert len(inter_building) >= 5
        f1 = next(
            (
                node
                for node in focus_map.get("nodes") or []
                if node.get("type") == "building"
                and "F1" in str(node.get("name") or "")
            ),
            None,
        )
        assert f1 is not None
        f1_edges = [
            edge
            for edge in inter_building
            if edge.get("from") == f1["id"] or edge.get("to") == f1["id"]
        ]
        assert len(f1_edges) >= 3
        connector_edges = [
            edge
            for edge in focus_map.get("edges") or []
            if edge.get("campusEdgeKind") == "connector"
        ]
        assert len(connector_edges) >= 1
        assert any(
            edge.get("from") == str(plaza.id) or edge.get("to") == str(plaza.id)
            for edge in connector_edges
        )
    finally:
        session.close()


@pytest.mark.postgres_integration
def test_hicampus_building_search_patch_highlights_f3_on_campus_layer():
    _require_postgres()
    from app.core.database import SessionLocal

    session = SessionLocal()
    try:
        building = (
            session.query(Node)
            .filter(
                Node.type_code == "building",
                Node.is_active == True,
                Node.attributes["world_id"].astext == "hicampus",
                Node.attributes["building_code"].astext == "F3",
            )
            .first()
        )
        gate = _node_by_package_id(session, "hicampus_gate")
        if not building or not gate:
            pytest.skip("HiCampus F3 building or gate not seeded; run world reload hicampus")

        map_patch = build_map_query_patch(
            session,
            [
                {
                    "entity_id": str(building.id),
                    "entity_type": "space",
                    "title": "F3 Training Center",
                }
            ],
            "F3",
        )
        assert map_patch.get("viewLayer") == "campus"
        assert str(building.id) in list(map_patch.get("highlightedNodeIds") or [])

        world = _node_by_package_id(session, "hicampus_world")
        assert world is not None
        focus_map = build_campus_focus_map(session, gate, world, mode="focus")
        highlighted = apply_highlight_ids_to_focus_map(
            focus_map,
            list(map_patch.get("highlightedNodeIds") or []),
        )
        active = [node for node in highlighted["nodes"] if node["status"] == "active"]
        assert any(node["id"] == str(building.id) for node in active)
    finally:
        session.close()


@pytest.mark.postgres_integration
def test_demo_world_upper_floor_map_uses_look_one_hop():
    """Any building floor uses the same floor-map contract (not F1-specific)."""
    _require_postgres()
    from app.core.database import SessionLocal

    session = SessionLocal()
    try:
        circulation = (
            session.query(Node)
            .filter(
                Node.type_code == "room",
                Node.is_active == True,
                Node.attributes["world_id"].astext == "hicampus",
                Node.attributes["package_node_id"].astext.like("%_02f_circulation_01"),
            )
            .first()
        )
        floor = None
        if circulation and circulation.location_id:
            floor = get_active_node(session, int(circulation.location_id))
        if not circulation or not floor:
            pytest.skip("HiCampus 2F circulation not seeded; run world reload hicampus")

        focus_map = build_floor_focus_map(session, circulation, floor)
        node_ids = {node["id"] for node in focus_map.get("nodes") or []}
        assert str(circulation.id) in node_ids
        edge_directions = {edge.get("direction") for edge in focus_map.get("edges") or []}
        assert "up" not in edge_directions
        assert "down" not in edge_directions
    finally:
        session.close()


@pytest.mark.postgres_integration
def test_hicampus_f1_floor_map_matches_look_one_hop():
    _require_postgres()
    from app.core.database import SessionLocal

    session = SessionLocal()
    try:
        circulation = _node_by_package_id(session, "hicampus_f1_01f_circulation_01")
        gate = _node_by_package_id(session, "hicampus_gate")
        plaza = _node_by_package_id(session, "hicampus_plaza")
        floor = (
            session.query(Node)
            .filter(
                Node.type_code == "building_floor",
                Node.is_active == True,
                Node.attributes["package_node_id"].astext == "hicampus_f1_01f",
            )
            .first()
        )
        if not all([circulation, gate, plaza, floor]):
            pytest.skip("HiCampus F1 floor graph not seeded; run world reload hicampus")

        focus_map = build_floor_focus_map(session, circulation, floor)
        node_ids = {node["id"] for node in focus_map.get("nodes") or []}
        bridge = _node_by_package_id(session, "hicampus_bridge")
        restroom = _node_by_package_id(session, "hicampus_f1_01f_restroom_01")
        electrical = _node_by_package_id(session, "hicampus_f1_01f_electrical_01")
        assert str(plaza.id) in node_ids
        assert str(gate.id) not in node_ids
        if bridge is not None:
            assert str(bridge.id) not in node_ids
        if restroom is not None:
            assert str(restroom.id) in node_ids
        if electrical is not None:
            assert str(electrical.id) in node_ids
        edge_directions = {edge.get("direction") for edge in focus_map.get("edges") or []}
        assert "up" not in edge_directions
        assert "down" not in edge_directions
        cross_edges = [edge for edge in focus_map.get("edges") or [] if edge.get("crossBuilding")]
        assert len(cross_edges) >= 3
    finally:
        session.close()
