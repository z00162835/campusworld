"""
F07: optional description sidecars, spatial row normalization, and P0 completeness checks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import yaml

from .contracts import DataPackageError, ERROR_WORLD_DATA_INVALID, ERROR_WORLD_DATA_REFERENCE_BROKEN

# ---------------------------------------------------------------------------
# P0 keys (non-empty string after strip) — see F07_SPATIAL_DESCRIPTION_CONTENT_PACK.md
# ---------------------------------------------------------------------------

ROOM_P0_STR = (
    "room_name",
    "room_name_en",
    "room_description",
    "room_short_description",
    "room_ambiance",
    "room_type",
    "room_code",
    "uns",
)

BUILDING_P0_STR = (
    "building_type",
    "building_status",
    "building_class",
    "uns",
    "building_name",
    "building_description",
    "building_tagline",
)

FLOOR_P0_STR = (
    "display_name",
    "floor_name",
    "floor_code",
    "uns",
    "floor_description",
    "floor_short_description",
)


def _read_optional_yaml(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"invalid yaml: {path.name} ({exc})") from exc


def _merge_by_id(rows: List[Dict[str, Any]], extras: List[Dict[str, Any]], *, kind: str) -> None:
    by_id = {str(r["id"]): r for r in rows if r.get("id")}
    for row in extras:
        if not isinstance(row, dict) or not row.get("id"):
            raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"{kind} sidecar row requires id")
        rid = str(row["id"])
        if rid not in by_id:
            raise DataPackageError(
                ERROR_WORLD_DATA_REFERENCE_BROKEN,
                f"{kind} sidecar id not in spatial package: {rid}",
            )
        target = by_id[rid]
        for k, v in row.items():
            if k == "id":
                continue
            target[k] = v


def merge_description_sidecars(data_root: Path, spatial: Dict[str, Any]) -> None:
    """Merge optional content/descriptions/{buildings,floors,rooms}.yaml into spatial lists."""
    root = data_root / "content" / "descriptions"
    b_doc = _read_optional_yaml(root / "buildings.yaml")
    f_doc = _read_optional_yaml(root / "floors.yaml")
    r_doc = _read_optional_yaml(root / "rooms.yaml")
    if b_doc.get("buildings"):
        _merge_by_id(spatial["buildings"], b_doc["buildings"], kind="buildings")
    if f_doc.get("floors"):
        _merge_by_id(spatial["floors"], f_doc["floors"], kind="floors")
    if r_doc.get("rooms"):
        _merge_by_id(spatial["rooms"], r_doc["rooms"], kind="rooms")


def normalize_spatial_rows(spatial: Dict[str, Any]) -> None:
    """floor_no -> floor_number; sync building_floors from floors_total when omitted."""
    for f in spatial.get("floors") or []:
        if not isinstance(f, dict):
            continue
        if f.get("floor_number") is None and f.get("floor_no") is not None:
            try:
                f["floor_number"] = int(f["floor_no"])
            except (TypeError, ValueError) as exc:
                raise DataPackageError(
                    ERROR_WORLD_DATA_INVALID,
                    f"floor_no must be int-compatible: {f.get('id')}",
                ) from exc
    for b in spatial.get("buildings") or []:
        if not isinstance(b, dict):
            continue
        if "building_floors" not in b and b.get("floors_total") is not None:
            try:
                b["building_floors"] = int(b["floors_total"])
            except (TypeError, ValueError):
                pass


def _nonempty_str(row: Dict[str, Any], key: str) -> bool:
    v = row.get(key)
    return isinstance(v, str) and bool(v.strip())


def validate_spatial_p0(
    spatial: Dict[str, Any],
    *,
    required_room_ids: Set[str],
) -> None:
    """Fail validation if P0 narrative/identity keys missing (HiCampus baseline)."""
    buildings = spatial.get("buildings") or []
    floors = spatial.get("floors") or []
    rooms = spatial.get("rooms") or []
    room_by_id = {str(r["id"]): r for r in rooms if isinstance(r, dict) and r.get("id")}

    for rid in sorted(required_room_ids):
        row = room_by_id.get(rid)
        if not row:
            raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"required room missing in package: {rid}")
        missing = [k for k in ROOM_P0_STR if not _nonempty_str(row, k)]
        if missing:
            raise DataPackageError(
                ERROR_WORLD_DATA_INVALID,
                f"room {rid} missing required description keys: {missing}",
            )

    for b in buildings:
        if not isinstance(b, dict) or not b.get("id"):
            continue
        missing = [k for k in BUILDING_P0_STR if not _nonempty_str(b, k)]
        if missing:
            raise DataPackageError(
                ERROR_WORLD_DATA_INVALID,
                f"building {b.get('id')} missing required description keys: {missing}",
            )

    for f in floors:
        if not isinstance(f, dict) or not f.get("id"):
            continue
        missing = [k for k in FLOOR_P0_STR if not _nonempty_str(f, k)]
        fn_ok = f.get("floor_number") is not None
        if not fn_ok and f.get("floor_no") is not None:
            try:
                fn_ok = int(f["floor_no"]) >= 0
            except (TypeError, ValueError):
                fn_ok = False
        if not fn_ok:
            missing.append("floor_number_or_floor_no")
        if missing:
            raise DataPackageError(
                ERROR_WORLD_DATA_INVALID,
                f"floor {f.get('id')} missing required description keys: {missing}",
            )


def collect_spatial_completeness_gaps(
    spatial: Dict[str, Any],
    *,
    required_room_ids: Set[str],
) -> Tuple[List[str], List[str], List[str]]:
    """
    Non-failing report: returns three lists of human-readable gap lines
    (buildings, floors, rooms). Used by world content diff / validate --report.
    """
    gaps_b: List[str] = []
    gaps_f: List[str] = []
    gaps_r: List[str] = []

    for b in spatial.get("buildings") or []:
        if not isinstance(b, dict) or not b.get("id"):
            continue
        missing = [k for k in BUILDING_P0_STR if not _nonempty_str(b, k)]
        if missing:
            gaps_b.append(f"{b.get('id')}: missing {missing}")

    for f in spatial.get("floors") or []:
        if not isinstance(f, dict) or not f.get("id"):
            continue
        missing = [k for k in FLOOR_P0_STR if not _nonempty_str(f, k)]
        fn_ok = f.get("floor_number") is not None
        if not fn_ok and f.get("floor_no") is not None:
            try:
                fn_ok = int(f["floor_no"]) >= 0
            except (TypeError, ValueError):
                fn_ok = False
        if not fn_ok:
            missing.append("floor_number_or_floor_no")
        if missing:
            gaps_f.append(f"{f.get('id')}: missing {missing}")

    room_by_id = {str(r["id"]): r for r in (spatial.get("rooms") or []) if isinstance(r, dict) and r.get("id")}
    for rid in sorted(required_room_ids):
        row = room_by_id.get(rid)
        if not row:
            gaps_r.append(f"{rid}: row missing")
            continue
        missing = [k for k in ROOM_P0_STR if not _nonempty_str(row, k)]
        if missing:
            gaps_r.append(f"{rid}: missing {missing}")

    return gaps_b, gaps_f, gaps_r
