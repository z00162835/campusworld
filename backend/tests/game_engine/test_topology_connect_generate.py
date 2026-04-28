"""HiCampus topology_connect_generate hub selection and dry-run."""

from __future__ import annotations

from collections import defaultdict

import pytest

from app.games.hicampus.package.topology_connect_generate import _hub_id_for_floor, generate_topology


@pytest.mark.game
@pytest.mark.unit
def test_hub_prefers_trailing_circulation_01_not_bridge():
    on_floor = [
        {"id": "hicampus_bridge", "floor_id": "hicampus_f1_01f", "room_type": "circulation"},
        {
            "id": "hicampus_f1_01f_circulation_01",
            "floor_id": "hicampus_f1_01f",
            "tags": ["space:circulation"],
        },
    ]
    assert _hub_id_for_floor(on_floor) == "hicampus_f1_01f_circulation_01"


@pytest.mark.game
@pytest.mark.unit
def test_generate_topology_connects_are_tagged_and_sized():
    _, connects, _ = generate_topology()
    assert len(connects) >= 400
    assert all(c.get("attributes", {}).get("topology_auto") for c in connects)


@pytest.mark.game
@pytest.mark.unit
def test_generate_topology_no_duplicate_direction_per_source():
    _, connects, _ = generate_topology()
    grouped = defaultdict(list)
    for rel in connects:
        src = str(rel.get("source_id") or "")
        d = str((rel.get("attributes") or {}).get("direction") or "")
        if src and d:
            grouped[(src, d)].append(str(rel.get("target_id") or ""))
    conflicts = {k: v for k, v in grouped.items() if len(v) > 1}
    assert conflicts == {}


@pytest.mark.game
@pytest.mark.unit
def test_generate_topology_never_connects_bridge_to_electrical():
    _, connects, _ = generate_topology()
    bad = [
        c
        for c in connects
        if str(c.get("source_id") or "") == "hicampus_bridge"
        and str(c.get("target_id") or "") == "hicampus_f1_01f_electrical_01"
    ]
    assert bad == []
