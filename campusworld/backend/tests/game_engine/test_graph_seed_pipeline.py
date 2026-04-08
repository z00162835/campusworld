"""Graph seed pipeline tests."""

from __future__ import annotations

import uuid
from typing import Any, Dict, FrozenSet

import pytest
from sqlalchemy import text

from app.game_engine.graph_seed.errors import GraphSeedError
from app.game_engine.graph_seed.ids import NAMESPACE_GRAPH_SEED, node_uuid
from app.game_engine.graph_seed.pipeline import run_graph_seed
from app.game_engine.runtime_store import WorldErrorCode


@pytest.mark.game
@pytest.mark.unit
def test_node_uuid_deterministic():
    u1 = node_uuid("hicampus", "hicampus_gate")
    u2 = node_uuid("hicampus", "hicampus_gate")
    assert u1 == u2
    assert u1.version == 5


@pytest.mark.game
@pytest.mark.unit
def test_node_uuid_namespace_stable():
    expected = uuid.uuid5(NAMESPACE_GRAPH_SEED, "hicampus:hicampus_gate")
    assert node_uuid("hicampus", "hicampus_gate") == expected


@pytest.mark.game
@pytest.mark.unit
def test_hicampus_profile_unknown_type_raises():
    from app.games.hicampus.package.graph_profile import HiCampusGraphProfile

    profile = HiCampusGraphProfile()
    with pytest.raises(GraphSeedError) as exc:
        profile.map_node_type("not_a_real_type")
    assert exc.value.error_code == WorldErrorCode.GRAPH_SEED_TYPE_UNKNOWN.value


@pytest.mark.game
@pytest.mark.unit
def test_hicampus_profile_maps_furniture_one_to_one():
    from app.games.hicampus.package.graph_profile import HiCampusGraphProfile

    assert HiCampusGraphProfile().map_node_type("furniture") == "furniture"


class _MiniWorldProfile:
    world_package_id_prop = "graph_seed_test"

    @property
    def world_package_id(self) -> str:
        return self.world_package_id_prop

    @property
    def strict_relationships(self) -> bool:
        return False

    @property
    def allowed_relationship_type_codes(self) -> FrozenSet[str]:
        return frozenset({"connects_to"})

    def map_node_type(self, package_type_code: str) -> str:
        m = {"world": "world", "building": "building", "building_floor": "building_floor", "room": "room"}
        if package_type_code not in m:
            raise GraphSeedError(
                WorldErrorCode.GRAPH_SEED_TYPE_UNKNOWN.value,
                f"unknown {package_type_code}",
            )
        return m[package_type_code]


class _MiniWorldProfileWithLocatedIn:
    world_package_id_prop = "graph_seed_test"

    @property
    def world_package_id(self) -> str:
        return self.world_package_id_prop

    @property
    def strict_relationships(self) -> bool:
        return False

    @property
    def allowed_relationship_type_codes(self) -> FrozenSet[str]:
        return frozenset({"connects_to", "located_in"})

    def map_node_type(self, package_type_code: str) -> str:
        m = {
            "world": "world",
            "building": "building",
            "building_floor": "building_floor",
            "room": "room",
            "furniture": "furniture",
        }
        if package_type_code not in m:
            raise GraphSeedError(
                WorldErrorCode.GRAPH_SEED_TYPE_UNKNOWN.value,
                f"unknown {package_type_code}",
            )
        return m[package_type_code]


def _minimal_snapshot() -> Dict[str, Any]:
    return {
        "world": {
            "id": "gst_world",
            "world_id": "graph_seed_test",
            "type_code": "world",
            "display_name": "GraphSeedTest",
            "tags": [],
            "attributes": {},
        },
        "spatial": {
            "buildings": [
                {
                    "id": "gst_b1",
                    "world_id": "graph_seed_test",
                    "building_code": "B1",
                    "type_code": "building",
                    "display_name": "B1",
                    "floors_total": 1,
                    "tags": [],
                }
            ],
            "floors": [
                {
                    "id": "gst_f1",
                    "world_id": "graph_seed_test",
                    "building_id": "gst_b1",
                    "floor_no": 1,
                    "type_code": "building_floor",
                }
            ],
            "rooms": [
                {
                    "id": "gst_r1",
                    "world_id": "graph_seed_test",
                    "floor_id": "gst_f1",
                    "type_code": "room",
                    "display_name": "R1",
                },
                {
                    "id": "gst_r2",
                    "world_id": "graph_seed_test",
                    "floor_id": "gst_f1",
                    "type_code": "room",
                    "display_name": "R2",
                },
            ],
        },
        "entities": {"npcs": [], "items": [], "zones": []},
        "relationships": [
            {
                "id": "gst_rel_one_way",
                "rel_type_code": "connects_to",
                "source_id": "gst_r1",
                "target_id": "gst_r2",
                "directed": True,
                "attributes": {},
            }
        ],
        "meta": {},
    }


def _require_postgres_engine():
    from app.core.database import engine

    if engine is None:
        pytest.skip("database engine not configured")
    if "postgresql" not in str(engine.url):
        pytest.skip("graph seed integration tests require PostgreSQL")


def _cleanup_test_graph(world_key: str) -> None:
    from app.core.database import db_session_context

    with db_session_context() as session:
        session.execute(
            text(
                """
                DELETE FROM relationships
                WHERE source_id IN (
                    SELECT id FROM nodes WHERE attributes->>'world_id' = :w
                )
                   OR target_id IN (
                    SELECT id FROM nodes WHERE attributes->>'world_id' = :w
                )
                """
            ),
            {"w": world_key},
        )
        session.execute(
            text("DELETE FROM nodes WHERE attributes->>'world_id' = :w"),
            {"w": world_key},
        )
        session.commit()


@pytest.mark.game
@pytest.mark.integration
def test_run_graph_seed_creates_reverse_connects_to():
    _require_postgres_engine()
    from app.core.database import db_session_context, engine
    from db.schema_migrations import ensure_graph_seed_ontology

    ensure_graph_seed_ontology(engine)
    world_key = "graph_seed_test"
    _cleanup_test_graph(world_key)

    profile = _MiniWorldProfile()
    snap = _minimal_snapshot()
    try:
        with db_session_context() as session:
            out = run_graph_seed(session, world_key, snap, profile)  # type: ignore[arg-type]
            session.commit()
        assert out["ok"] is True
        d = out["details"]
        assert d["nodes_upserted"] >= 5
        assert d["relationships_created"] == 2
        assert d.get("relationships_ignored_count") == 0
        assert d.get("strict_relationships") is False

        with db_session_context() as session:
            cnt = session.execute(
                text(
                    """
                    SELECT count(*) FROM relationships r
                    JOIN nodes s ON s.id = r.source_id
                    JOIN nodes t ON t.id = r.target_id
                    WHERE r.type_code = 'connects_to'
                      AND s.attributes->>'package_node_id' = 'gst_r1'
                      AND t.attributes->>'package_node_id' = 'gst_r2'
                    """
                )
            ).scalar()
            cnt_rev = session.execute(
                text(
                    """
                    SELECT count(*) FROM relationships r
                    JOIN nodes s ON s.id = r.source_id
                    JOIN nodes t ON t.id = r.target_id
                    WHERE r.type_code = 'connects_to'
                      AND s.attributes->>'package_node_id' = 'gst_r2'
                      AND t.attributes->>'package_node_id' = 'gst_r1'
                    """
                )
            ).scalar()
        assert int(cnt or 0) == 1
        assert int(cnt_rev or 0) == 1
    finally:
        _cleanup_test_graph(world_key)


@pytest.mark.game
@pytest.mark.integration
def test_run_graph_seed_located_in_sets_location_id():
    _require_postgres_engine()
    from app.core.database import db_session_context, engine
    from db.schema_migrations import ensure_graph_seed_ontology

    ensure_graph_seed_ontology(engine)
    world_key = "graph_seed_test"
    _cleanup_test_graph(world_key)

    profile = _MiniWorldProfileWithLocatedIn()
    snap = _minimal_snapshot()
    snap["entities"] = {
        "npcs": [],
        "items": [
            {
                "id": "gst_item_bench",
                "world_id": world_key,
                "type_code": "furniture",
                "entity_kind": "item",
                "display_name": "Test Bench",
                "location_ref": "gst_r1",
                "attributes": {"item_kind": "furniture"},
                "presentation_domains": ["room"],
                "access_locks": {"view": "all()", "interact": "all()"},
                "tags": ["item", "furniture"],
                "source_ref": "entities/items.yaml",
            }
        ],
        "zones": [],
    }
    snap["relationships"] = list(snap["relationships"]) + [
        {
            "id": "gst_rel_located_in_item",
            "rel_type_code": "located_in",
            "source_id": "gst_item_bench",
            "target_id": "gst_r1",
            "directed": True,
            "attributes": {},
        }
    ]
    try:
        with db_session_context() as session:
            out = run_graph_seed(session, world_key, snap, profile)  # type: ignore[arg-type]
            session.commit()
        assert out["ok"] is True

        with db_session_context() as session:
            loc_bench = session.execute(
                text(
                    """
                    SELECT id, location_id FROM nodes
                    WHERE type_code = 'furniture'
                      AND attributes->>'package_node_id' = 'gst_item_bench'
                    """
                )
            ).mappings().first()
            loc_room = session.execute(
                text(
                    """
                    SELECT id FROM nodes
                    WHERE type_code = 'room'
                      AND attributes->>'package_node_id' = 'gst_r1'
                    """
                )
            ).scalar()
        assert loc_bench is not None
        assert loc_room is not None
        assert int(loc_bench["location_id"]) == int(loc_room)
    finally:
        _cleanup_test_graph(world_key)


@pytest.mark.game
@pytest.mark.integration
def test_run_graph_seed_counts_ignored_relationship_types():
    _require_postgres_engine()
    from app.core.database import db_session_context, engine
    from db.schema_migrations import ensure_graph_seed_ontology

    ensure_graph_seed_ontology(engine)
    world_key = "graph_seed_test"
    _cleanup_test_graph(world_key)

    profile = _MiniWorldProfile()
    snap = _minimal_snapshot()
    snap["relationships"] = list(snap["relationships"]) + [
        {
            "id": "gst_rel_governs",
            "rel_type_code": "governs",
            "source_id": "gst_r1",
            "target_id": "gst_r2",
            "directed": True,
            "attributes": {},
        }
    ]
    try:
        with db_session_context() as session:
            out = run_graph_seed(session, world_key, snap, profile)  # type: ignore[arg-type]
            session.commit()
        assert out["details"]["relationships_ignored_count"] >= 1
        assert "governs" in out["details"].get("relationships_ignored_by_type", {})
    finally:
        _cleanup_test_graph(world_key)


@pytest.mark.game
@pytest.mark.integration
def test_run_graph_seed_strict_rejects_unsupported_relationship():
    _require_postgres_engine()
    from app.core.database import db_session_context, engine
    from db.schema_migrations import ensure_graph_seed_ontology

    ensure_graph_seed_ontology(engine)
    world_key = "graph_seed_test"
    _cleanup_test_graph(world_key)

    profile = _MiniWorldProfile()
    snap = _minimal_snapshot()
    snap["relationships"] = list(snap["relationships"]) + [
        {
            "id": "gst_rel_governs",
            "rel_type_code": "governs",
            "source_id": "gst_r1",
            "target_id": "gst_r2",
            "directed": True,
            "attributes": {},
        }
    ]
    try:
        with db_session_context() as session:
            with pytest.raises(GraphSeedError) as exc:
                run_graph_seed(
                    session,
                    world_key,
                    snap,
                    profile,  # type: ignore[arg-type]
                    strict_relationships=True,
                )
        assert exc.value.error_code == WorldErrorCode.GRAPH_SEED_RELATIONSHIP_UNSUPPORTED.value
    finally:
        _cleanup_test_graph(world_key)


@pytest.mark.game
@pytest.mark.integration
def test_run_graph_seed_second_run_idempotent():
    _require_postgres_engine()
    from app.core.database import db_session_context, engine
    from db.schema_migrations import ensure_graph_seed_ontology

    ensure_graph_seed_ontology(engine)
    world_key = "graph_seed_test"
    _cleanup_test_graph(world_key)

    profile = _MiniWorldProfile()
    snap = _minimal_snapshot()
    try:
        with db_session_context() as session:
            first = run_graph_seed(session, world_key, snap, profile)  # type: ignore[arg-type]
            session.commit()
        assert first["details"]["nodes_upserted"] >= 1

        with db_session_context() as session:
            second = run_graph_seed(session, world_key, snap, profile)  # type: ignore[arg-type]
            session.commit()
        assert second["details"]["nodes_skipped"] >= first["details"]["nodes_upserted"]
        assert second["details"]["relationships_skipped"] >= first["details"]["relationships_created"]
    finally:
        _cleanup_test_graph(world_key)


@pytest.mark.game
@pytest.mark.unit
def test_entity_row_flat_attributes_merges_nested_yaml_attributes():
    from app.game_engine.graph_seed.pipeline import _entity_row_flat_attributes

    row: Dict[str, Any] = {
        "id": "fixture_01",
        "type_code": "lighting_fixture",
        "display_name": "Building · 照明回路",
        "world_id": "hicampus",
        "tags": [],
        "entity_kind": "item",
        "location_ref": "room_a",
        "attributes": {"room_list_name": "照明回路", "power_on": True},
    }
    flat = _entity_row_flat_attributes(row)
    assert flat["room_list_name"] == "照明回路"
    assert flat["power_on"] is True
    assert flat["entity_kind"] == "item"
    assert flat["location_ref"] == "room_a"
    assert "display_name" not in flat
    assert "attributes" not in flat


@pytest.mark.game
@pytest.mark.integration
def test_ensure_graph_seed_ontology_applies_yaml_schema_definitions():
    """Ontology YAML overlays must be written to node_types on ensure_graph_seed_ontology."""
    _require_postgres_engine()
    from sqlalchemy import text

    from app.core.database import db_session_context, engine
    from db.schema_migrations import ensure_graph_seed_ontology

    ensure_graph_seed_ontology(engine)
    with db_session_context() as session:
        row = session.execute(
            text("SELECT schema_definition, tags FROM node_types WHERE type_code = 'network_access_point'")
        ).fetchone()
    assert row is not None
    sd, tags = row[0], row[1]
    assert isinstance(sd, dict)
    assert sd.get("type") == "object"
    assert "properties" in sd
    assert "graph_seed" in (tags or [])


@pytest.mark.game
@pytest.mark.integration
def test_ensure_graph_seed_ontology_room_schema_from_yaml():
    _require_postgres_engine()
    from sqlalchemy import text

    from app.core.database import db_session_context, engine
    from db.schema_migrations import ensure_graph_seed_ontology

    ensure_graph_seed_ontology(engine)
    with db_session_context() as session:
        row = session.execute(
            text("SELECT schema_definition FROM node_types WHERE type_code = 'room'")
        ).fetchone()
    assert row is not None
    sd = row[0]
    assert isinstance(sd, dict)
    assert sd.get("type") == "object"
    assert "room_type" in sd.get("properties", {})


@pytest.mark.game
@pytest.mark.integration
def test_ensure_graph_seed_ontology_parent_type_codes_match_python_mro():
    """T9: node_types.parent_type_code aligns with GRAPH_SEED_NODE_TYPES_MATRIX."""
    _require_postgres_engine()
    from app.core.database import db_session_context, engine
    from db.schema_migrations import GRAPH_SEED_ONTOLOGY_NODE_ROWS, ensure_graph_seed_ontology

    ensure_graph_seed_ontology(engine)
    expected = {row[0]: row[1] for row in GRAPH_SEED_ONTOLOGY_NODE_ROWS}
    with db_session_context() as session:
        rows = session.execute(text("SELECT type_code, parent_type_code FROM node_types")).fetchall()
    got = {r[0]: r[1] for r in rows if r[0] in expected}
    assert got == expected


@pytest.mark.game
@pytest.mark.integration
def test_ensure_builtin_node_type_schema_envelopes_idempotent():
    """T5: builtin node_types rows use JSON Schema object envelope when present."""
    _require_postgres_engine()
    from db.ontology.schema_envelope import is_json_schema_object_envelope
    from db.schema_migrations import ensure_builtin_node_type_schema_envelopes

    from app.core.database import db_session_context, engine

    ensure_builtin_node_type_schema_envelopes(engine)
    ensure_builtin_node_type_schema_envelopes(engine)
    with db_session_context() as session:
        for tc in ("account", "system_command_ability", "system_notice"):
            row = session.execute(
                text("SELECT schema_definition FROM node_types WHERE type_code = :tc"),
                {"tc": tc},
            ).fetchone()
            if row is None:
                continue
            assert is_json_schema_object_envelope(row[0]), f"{tc} should be envelope after ensure"
