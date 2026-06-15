#!/usr/bin/env python3
"""Validate spatial map hierarchy for world packages and optional DB-backed nodes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def _load_package_snapshot(world_id: str) -> Dict[str, Any]:
    if world_id == "hicampus":
        from app.games.hicampus import load_package_snapshot

        data_root = project_root / "app" / "games" / "hicampus" / "data"
        snap = load_package_snapshot(str(data_root))
        return {
            "world": snap.world,
            "spatial": snap.spatial,
        }
    raise SystemExit(f"Unsupported world package for validation: {world_id}")


OUTDOOR_SPINE_ROOM_IDS = ("hicampus_gate", "hicampus_bridge", "hicampus_plaza")


def _validate_outdoor_spine(rooms: List[Dict[str, Any]], buildings: List[Dict[str, Any]]) -> List[str]:
    """Gate → bridge → plaza on one column; no building between gate and bridge."""
    errors: List[str] = []
    outdoors = {str(r.get("id")): r for r in rooms if str(r.get("id")) in OUTDOOR_SPINE_ROOM_IDS}
    if len(outdoors) < 3:
        return errors
    gate = outdoors["hicampus_gate"]
    bridge = outdoors["hicampus_bridge"]
    plaza = outdoors["hicampus_plaza"]
    try:
        gate_row = int(gate.get("campus_grid_row"))
        bridge_row = int(bridge.get("campus_grid_row"))
        plaza_row = int(plaza.get("campus_grid_row"))
        spine_col = int(gate.get("campus_grid_col"))
    except (TypeError, ValueError):
        errors.append("outdoor spine rooms missing campus_grid_col/row")
        return errors
    if not (plaza_row < bridge_row < gate_row):
        errors.append(
            f"outdoor spine row order invalid: plaza={plaza_row}, bridge={bridge_row}, gate={gate_row} "
            "(expected plaza < bridge < gate, north-up)"
        )
    for rid in ("hicampus_bridge", "hicampus_plaza"):
        other = outdoors[rid]
        if int(other.get("campus_grid_col")) != spine_col:
            errors.append(f"{rid} campus_grid_col must match gate spine column {spine_col}")
    for building in buildings:
        bid = str(building.get("id") or "")
        try:
            bcol = int(building.get("campus_grid_col"))
            brow = int(building.get("campus_grid_row"))
        except (TypeError, ValueError):
            continue
        if bcol == spine_col and bridge_row < brow < gate_row:
            errors.append(
                f"building {bid} blocks outdoor spine at col {spine_col} row {brow} "
                f"(between bridge row {bridge_row} and gate row {gate_row})"
            )
    return errors


def validate_package_hierarchy(snapshot: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    spatial = snapshot.get("spatial") or {}
    buildings_list = spatial.get("buildings") or []
    buildings = {str(b["id"]): b for b in buildings_list if isinstance(b, dict) and b.get("id")}
    floors = {str(f["id"]): f for f in spatial.get("floors") or [] if isinstance(f, dict) and f.get("id")}
    rooms = [r for r in spatial.get("rooms") or [] if isinstance(r, dict) and r.get("id")]

    errors.extend(_validate_outdoor_spine(rooms, buildings_list))

    world_row = snapshot.get("world") or {}
    world_slug = str(world_row.get("world_id") or "").strip()
    world_logical_id = str(world_row.get("id") or "").strip()

    for fid, floor in floors.items():
        display = str(floor.get("display_name") or floor.get("floor_name") or "").strip()
        if not display:
            errors.append(f"floor {fid}: missing display_name/floor_name")
        bid = str(floor.get("building_id") or "").strip()
        if not bid:
            errors.append(f"floor {fid}: missing building_id")
        elif bid not in buildings:
            errors.append(f"floor {fid}: building_id {bid} not found")
        wid = str(floor.get("world_id") or "").strip()
        if world_slug and wid and wid != world_slug:
            errors.append(f"floor {fid}: world_id {wid} != package world {world_slug}")

    for bid, building in buildings.items():
        wid = str(building.get("world_id") or "").strip()
        if world_slug and wid and wid != world_slug:
            errors.append(f"building {bid}: world_id {wid} != package world {world_slug}")
        if not str(building.get("display_name") or building.get("building_name") or "").strip():
            errors.append(f"building {bid}: missing display_name/building_name")

    if world_slug and world_logical_id and world_slug != world_logical_id:
        # Document expected slug vs logical id; buildings reference slug.
        pass

    floor_building: Dict[str, str] = {}
    for fid, floor in floors.items():
        floor_building[fid] = str(floor.get("building_id") or "").strip()

    for room in rooms:
        rid = str(room.get("id"))
        fid = str(room.get("floor_id") or "").strip()
        if not fid:
            errors.append(f"room {rid}: missing floor_id")
            continue
        if fid not in floors:
            errors.append(f"room {rid}: floor_id {fid} not found")
            continue
        expected_building = floor_building.get(fid, "")
        building_row = buildings.get(expected_building, {})
        room_building = str(room.get("room_building") or room.get("building_id") or "").strip()
        valid_building_labels = {
            str(building_row.get("display_name") or "").strip(),
            str(building_row.get("building_name") or "").strip(),
            str(building_row.get("building_name_en") or "").strip(),
            expected_building,
        }
        valid_building_labels.discard("")
        if room_building and valid_building_labels and room_building not in valid_building_labels:
            errors.append(
                f"room {rid}: room_building {room_building!r} not in {sorted(valid_building_labels)!r}"
            )

    return errors


def validate_db_hierarchy(world_id: str) -> List[str]:
    from sqlalchemy import text

    from app.core.database import db_session_context, engine

    if engine is None:
        return ["database engine not configured"]

    errors: List[str] = []
    with db_session_context() as session:
        buildings = session.execute(
            text(
                """
                SELECT id, name, location_id, attributes
                FROM nodes
                WHERE type_code = 'building'
                  AND is_active = TRUE
                  AND attributes->>'world_id' = :wid
                """
            ),
            {"wid": world_id},
        ).mappings().all()

        world_nodes = session.execute(
            text(
                """
                SELECT id, name, attributes
                FROM nodes
                WHERE type_code = 'world'
                  AND is_active = TRUE
                  AND attributes->>'world_id' = :wid
                """
            ),
            {"wid": world_id},
        ).mappings().all()
        world_ids: Set[int] = {int(row["id"]) for row in world_nodes}

        for row in buildings:
            loc = row.get("location_id")
            if not loc or int(loc) not in world_ids:
                pkg = (row.get("attributes") or {}).get("package_node_id") or row["name"]
                errors.append(f"building node {row['id']} ({pkg}): location_id not linked to world")

        floors = session.execute(
            text(
                """
                SELECT id, name, location_id, attributes
                FROM nodes
                WHERE type_code = 'building_floor'
                  AND is_active = TRUE
                  AND attributes->>'world_id' = :wid
                """
            ),
            {"wid": world_id},
        ).mappings().all()

        building_by_pkg: Dict[str, int] = {}
        for row in buildings:
            attrs = row.get("attributes") or {}
            pkg = str(attrs.get("package_node_id") or "").strip()
            if pkg:
                building_by_pkg[pkg] = int(row["id"])

        for row in floors:
            attrs = row.get("attributes") or {}
            display = str(attrs.get("display_name") or attrs.get("floor_name") or row["name"] or "").strip()
            if display.startswith("hicampus_") and " · " not in display:
                errors.append(f"floor node {row['id']}: display looks like package id ({display})")
            bid = str(attrs.get("building_id") or "").strip()
            parent_id = int(row["location_id"] or 0)
            expected_parent = building_by_pkg.get(bid)
            if expected_parent and parent_id != expected_parent:
                errors.append(
                    f"floor node {row['id']}: location_id {parent_id} != building {expected_parent} for {bid}"
                )

        rooms = session.execute(
            text(
                """
                SELECT id, name, location_id, attributes
                FROM nodes
                WHERE type_code = 'room'
                  AND is_active = TRUE
                  AND attributes->>'world_id' = :wid
                """
            ),
            {"wid": world_id},
        ).mappings().all()

        floor_by_pkg: Dict[str, int] = {}
        for row in floors:
            attrs = row.get("attributes") or {}
            pkg = str(attrs.get("package_node_id") or "").strip()
            if pkg:
                floor_by_pkg[pkg] = int(row["id"])

        for row in rooms:
            attrs = row.get("attributes") or {}
            fid = str(attrs.get("floor_id") or "").strip()
            parent_id = int(row["location_id"] or 0)
            expected_parent = floor_by_pkg.get(fid)
            if expected_parent and parent_id != expected_parent:
                errors.append(
                    f"room node {row['id']}: location_id {parent_id} != floor {expected_parent} for {fid}"
                )

    return errors


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate map spatial hierarchy for a world package")
    parser.add_argument("--world", default="hicampus", help="World package id (default: hicampus)")
    parser.add_argument("--check-db", action="store_true", help="Also validate PostgreSQL node.location_id chains")
    args = parser.parse_args(argv)

    print(f"Validating package hierarchy for world={args.world}...")
    snapshot = _load_package_snapshot(args.world)
    errors = validate_package_hierarchy(snapshot)

    if args.check_db:
        print(f"Validating DB hierarchy for world_id={args.world}...")
        errors.extend(validate_db_hierarchy(args.world))

    if errors:
        print(f"Found {len(errors)} issue(s):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("Map hierarchy validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
