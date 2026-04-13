"""HiCampus spatial description merge, P0 validation, and overlay helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from app.games.hicampus.package.content_merge import (
    BUILDING_P0_STR,
    merge_description_sidecars,
    normalize_spatial_rows,
    validate_spatial_p0,
)
from app.games.hicampus.package.content_overlay import content_validate_report
from app.games.hicampus.package.contracts import DataPackageError, ERROR_WORLD_DATA_INVALID
from app.games.hicampus.package.validator import validate_data_package

DATA_ROOT = Path(__file__).resolve().parents[2] / "app" / "games" / "hicampus" / "data"


@pytest.mark.game
@pytest.mark.unit
def test_normalize_spatial_rows_sets_floor_number_and_building_floors():
    spatial = {
        "floors": [{"id": "f1", "floor_no": 2}],
        "buildings": [{"id": "b1", "floors_total": 5}],
    }
    normalize_spatial_rows(spatial)
    assert spatial["floors"][0]["floor_number"] == 2
    assert spatial["buildings"][0]["building_floors"] == 5


@pytest.mark.game
@pytest.mark.unit
def test_merge_description_sidecar_updates_row(tmp_path: Path):
    (tmp_path / "content" / "descriptions").mkdir(parents=True)
    (tmp_path / "content" / "descriptions" / "rooms.yaml").write_text(
        "rooms:\n  - id: r1\n    room_description: from sidecar\n",
        encoding="utf-8",
    )
    spatial = {"buildings": [], "floors": [], "rooms": [{"id": "r1", "display_name": "R"}]}
    merge_description_sidecars(tmp_path, spatial)
    assert spatial["rooms"][0]["room_description"] == "from sidecar"


@pytest.mark.game
@pytest.mark.unit
def test_validate_spatial_p0_rejects_empty_required_room():
    spatial = {
        "buildings": [{"id": "b1", **{k: "x" for k in BUILDING_P0_STR}}],
        "floors": [
            {
                "id": "f1",
                "display_name": "d",
                "floor_name": "n",
                "floor_code": "c",
                "uns": "u",
                "floor_description": "fd",
                "floor_short_description": "fs",
                "floor_no": 1,
            }
        ],
        "rooms": [{"id": "hicampus_gate", "display_name": "G"}],
    }
    normalize_spatial_rows(spatial)
    with pytest.raises(DataPackageError) as exc:
        validate_spatial_p0(spatial, required_room_ids={"hicampus_gate"})
    assert exc.value.error_code == ERROR_WORLD_DATA_INVALID


@pytest.mark.game
@pytest.mark.unit
def test_validate_data_package_hicampus_passes_p0():
    payload = validate_data_package(DATA_ROOT)
    gate = next(r for r in payload["spatial"]["rooms"] if r["id"] == "hicampus_gate")
    assert gate.get("room_description")
    f1 = next(f for f in payload["spatial"]["floors"] if f["id"] == "hicampus_f1_01f")
    assert f1.get("floor_number") == 1


@pytest.mark.game
@pytest.mark.unit
def test_content_validate_report_ok_on_full_package():
    rep = content_validate_report(DATA_ROOT)
    assert rep.get("ok") is True
    assert rep.get("room_gaps") == []


@pytest.mark.game
@pytest.mark.unit
def test_validate_fails_when_required_room_missing_p0(tmp_path: Path):
    dst = tmp_path / "data"
    shutil.copytree(DATA_ROOT, dst)
    rooms_path = dst / "rooms.yaml"
    doc = yaml.safe_load(rooms_path.read_text(encoding="utf-8")) or {}
    for row in doc.get("rooms") or []:
        if row.get("id") == "hicampus_gate":
            row["room_description"] = ""
            break
    rooms_path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    with pytest.raises(DataPackageError) as exc:
        validate_data_package(dst)
    assert exc.value.error_code == ERROR_WORLD_DATA_INVALID
