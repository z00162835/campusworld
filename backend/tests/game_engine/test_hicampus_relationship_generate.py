"""HiCampus relationship generation (Phase 3)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.games.hicampus.package.entity_relationship_generate import (
    generate_item_located_in_relationships,
    generate_npc_located_in_relationships,
    merge_relationships,
)


@pytest.mark.game
@pytest.mark.unit
def test_generate_item_located_in_relationships_basic(tmp_path: Path):
    (tmp_path / "entities").mkdir(parents=True)
    (tmp_path / "entities" / "items.yaml").write_text(
        yaml.safe_dump(
            {
                "items": [
                    {"id": "i1", "location_ref": "r1", "type_code": "network_access_point"},
                    {"id": "i2", "location_ref": "r1", "type_code": "lighting_fixture"},
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    out = generate_item_located_in_relationships(data_root=tmp_path)
    keys = {(r["rel_type_code"], r["source_id"], r["target_id"]) for r in out}
    assert ("located_in", "i1", "r1") in keys
    assert ("located_in", "i2", "r1") in keys


@pytest.mark.game
@pytest.mark.unit
def test_generate_npc_located_in_relationships_basic(tmp_path: Path):
    (tmp_path / "entities").mkdir(parents=True)
    (tmp_path / "entities" / "npcs.yaml").write_text(
        yaml.safe_dump(
            {"npcs": [{"id": "n1", "location_ref": "r9", "type_code": "npc_agent"}]},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    out = generate_npc_located_in_relationships(data_root=tmp_path)
    keys = {(r["rel_type_code"], r["source_id"], r["target_id"]) for r in out}
    assert ("located_in", "n1", "r9") in keys


@pytest.mark.game
@pytest.mark.unit
def test_merge_relationships_dedup_by_identity():
    existing = [
        {"id": "x", "rel_type_code": "located_in", "source_id": "i1", "target_id": "r1", "directed": True},
    ]
    additions = [
        {"id": "y", "rel_type_code": "located_in", "source_id": "i1", "target_id": "r1", "directed": True},
        {"id": "z", "rel_type_code": "located_in", "source_id": "i2", "target_id": "r1", "directed": True},
    ]
    merged, added = merge_relationships(existing, additions)
    assert added == 1
    assert len(merged) == 2

