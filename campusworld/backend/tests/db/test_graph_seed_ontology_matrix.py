"""T8: GRAPH_SEED_ONTOLOGY_NODE_ROWS invariants vs ontology matrix (unit, no DB)."""

from __future__ import annotations

import pytest

from db.schema_migrations import GRAPH_SEED_ONTOLOGY_NODE_ROWS


@pytest.mark.unit
def test_graph_seed_ontology_node_rows_parent_fk_closed():
    codes = [row[0] for row in GRAPH_SEED_ONTOLOGY_NODE_ROWS]
    seen: set[str] = set()
    for type_code, parent_code, *_ in GRAPH_SEED_ONTOLOGY_NODE_ROWS:
        assert type_code not in seen, f"duplicate type_code {type_code}"
        seen.add(type_code)
        if parent_code is None:
            continue
        assert parent_code in seen, f"{type_code} parent {parent_code} must appear earlier than child"
        assert parent_code in codes


@pytest.mark.unit
def test_graph_seed_ontology_node_rows_matches_matrix_targets():
    expected_parent = {
        "default_object": None,
        "world_thing": "default_object",
        "world": "default_object",
        "world_object": "default_object",
        "building": "default_object",
        "building_floor": "default_object",
        "room": "default_object",
        "world_entrance": "default_object",
        "furniture": "world_thing",
        "npc_agent": "world_thing",
        "logical_zone": "world_thing",
        "access_terminal": "world_thing",
        "network_access_point": "world_thing",
        "av_display": "world_thing",
        "lighting_fixture": "world_thing",
        "conference_seating": "furniture",
        "lounge_furniture": "furniture",
    }
    got = {row[0]: row[1] for row in GRAPH_SEED_ONTOLOGY_NODE_ROWS}
    assert got == expected_parent
