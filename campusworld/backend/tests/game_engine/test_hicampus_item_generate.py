"""HiCampus procedural entity items generation."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.games.hicampus.package.entity_item_generate import (
    _PRESERVED_ITEM_IDS,
    _build_item_row,
    generate_items,
    merge_items,
)

PKG = Path(__file__).resolve().parents[2] / "app" / "games" / "hicampus" / "package"
DATA_ROOT = Path(__file__).resolve().parents[2] / "app" / "games" / "hicampus" / "data"


@pytest.mark.game
@pytest.mark.unit
def test_generate_items_meeting_room_has_display_and_seating(tmp_path: Path):
    rooms = {
        "rooms": [
            {
                "id": "test_room_meet_01",
                "display_name": "Test Meeting",
                "tags": ["space:meeting", "room"],
            }
        ]
    }
    (tmp_path / "rooms.yaml").write_text(yaml.safe_dump(rooms, allow_unicode=True, sort_keys=False), encoding="utf-8")
    gen = generate_items(data_root=tmp_path, package_dir=PKG)
    types = {r["type_code"] for r in gen}
    assert "av_display" in types
    assert "conference_seating" in types
    assert "network_access_point" in types
    assert "lighting_fixture" in types


@pytest.mark.game
@pytest.mark.unit
def test_merge_keeps_preserves_and_skips_duplicate_ids(tmp_path: Path):
    preserved = [
        {
            "id": "hicampus_device_gate_terminal_01",
            "world_id": "hicampus",
            "type_code": "access_terminal",
            "entity_kind": "item",
            "display_name": "T",
            "location_ref": "hicampus_gate",
            "attributes": {},
            "presentation_domains": ["room"],
            "access_locks": {"view": "all()", "interact": "all()"},
            "tags": [],
            "source_ref": "entities/items.yaml",
        }
    ]
    gen = [{"id": "x1", "location_ref": "r1"}]
    m = merge_items(preserved, gen)
    assert len(m) == 2
    assert m[0]["id"] == "hicampus_device_gate_terminal_01"


@pytest.mark.game
@pytest.mark.unit
def test_preserved_ids_cover_hand_authored_items():
    assert "hicampus_device_gate_terminal_01" in _PRESERVED_ITEM_IDS
    assert "hicampus_furniture_bench_01" in _PRESERVED_ITEM_IDS


@pytest.mark.game
@pytest.mark.unit
def test_build_item_row_sets_room_list_name_when_display_uses_middle_dot():
    row = _build_item_row(
        template_key="lighting_fixture",
        template={
            "type_code": "lighting_fixture",
            "display_name_tpl": "{room_name} · 照明回路",
            "attributes": {"item_kind": "device", "device_role": "lighting"},
            "tags": ["item", "device"],
            "presentation_domains": ["room"],
            "access_locks": {"view": "all()", "interact": "all()"},
        },
        room={"id": "hicampus_bridge", "display_name": "HiCampus Bridge", "tags": ["room"]},
        seq=1,
        placement={
            "building_code": "F1",
            "floor_no": 1,
            "layer_role": "lobby",
            "building_type": "administrative",
            "layer": "public",
        },
    )
    assert row["display_name"] == "HiCampus Bridge · 照明回路"
    assert row["attributes"].get("room_list_name") == "照明回路"


@pytest.mark.game
@pytest.mark.unit
def test_full_data_root_generate_count_sane():
    gen = generate_items(data_root=DATA_ROOT, package_dir=PKG)
    n_rooms = len(yaml.safe_load((DATA_ROOT / "rooms.yaml").read_text(encoding="utf-8")).get("rooms") or [])
    assert len(gen) >= n_rooms * 2


@pytest.mark.game
@pytest.mark.unit
def test_generate_enriches_from_floor_layer_role():
    gen = generate_items(data_root=DATA_ROOT, package_dir=PKG)
    ap = next(
        r
        for r in gen
        if r["location_ref"] == "hicampus_f1_17f_meeting_01" and r["type_code"] == "network_access_point"
    )
    assert ap["attributes"]["placement"]["layer_role"] == "meeting_heavy"
    assert ap["attributes"]["placement"]["building_code"] == "F1"
    assert ap["attributes"]["network"]["ssid"] == "HiCampus-F1-L17"

    seating = next(r for r in gen if r["id"] == "hicampus_f1_17f_meeting_01_conference_seating_01")
    assert seating["attributes"]["seat_count"] == 12
    assert seating["attributes"].get("layout") == "u_shape"

    display = next(
        r for r in gen if r["location_ref"] == "hicampus_f1_17f_meeting_01" and r["type_code"] == "av_display"
    )
    assert display["attributes"]["av"].get("brightness_nit") == 450
