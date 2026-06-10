"""PostgreSQL integration tests for semantic map against seeded HiCampus graph."""

from __future__ import annotations

import pytest
from app.models.graph import Node
from app.services.world_interaction.semantic_map_service import (
    apply_highlight_ids_to_focus_map,
    build_campus_focus_map,
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
        assert len(focus_map.get("edges") or []) >= 2
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
