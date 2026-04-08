"""
Generate per-floor circulation hubs, horizontal connects_to (star+chain), and
vertical up/down chains per building for HiCampus.

Preserves manual outdoor/plaza spine rels; replaces all other connects_to.
Run from backend:  python -m app.games.hicampus.package.topology_connect_generate --write
Then:             python -m app.games.hicampus.package.entity_relationship_generate --write
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

_PACKAGE_DIR = Path(__file__).resolve().parent
_DATA_ROOT = _PACKAGE_DIR.parent / "data"

# Manual spine: gate/bridge/plaza + F1 首层交通核↔广场/卫生间
PRESERVE_CONNECT_IDS: Set[str] = {
    "rel_gate_bridge",
    "rel_bridge_gate",
    "rel_bridge_plaza",
    "rel_plaza_bridge",
    "rel_plaza_f1_circulation",
    "rel_f1_circulation_plaza",
    "rel_circulation_restroom_w",
    "rel_restroom_circulation_e",
}

LANDMARK_ROOM_IDS: Set[str] = {"hicampus_gate", "hicampus_bridge", "hicampus_plaza"}

# 连桥等 room_type 也可能是 circulation，不得作为楼层交通核
_NOT_FLOOR_HUB_IDS: Set[str] = {"hicampus_bridge"}

DIR_ORDER: List[str] = [
    "north",
    "west",
    "east",
    "south",
    "northeast",
    "northwest",
    "southeast",
    "southwest",
]

OPPOSITE: Dict[str, str] = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "northeast": "southwest",
    "southwest": "northeast",
    "northwest": "southeast",
    "southeast": "northwest",
    "up": "down",
    "down": "up",
}


def _connect_pair(src: str, tgt: str, d_fwd: str) -> List[Dict[str, Any]]:
    """Return two directed connects_to rels with opposite directions."""
    d_rev = OPPOSITE[d_fwd]
    return [
        {
            "id": _rel_topo_id(src, tgt, d_fwd),
            "rel_type_code": "connects_to",
            "source_id": src,
            "target_id": tgt,
            "directed": True,
            "attributes": {"direction": d_fwd, "topology_auto": True},
        },
        {
            "id": _rel_topo_id(tgt, src, d_rev),
            "rel_type_code": "connects_to",
            "source_id": tgt,
            "target_id": src,
            "directed": True,
            "attributes": {"direction": d_rev, "topology_auto": True},
        },
    ]


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _short_hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]


def _rel_topo_id(source: str, target: str, direction: str) -> str:
    return f"rel_topo_{_short_hash(f'{source}|{target}|{direction}')}"


def _floor_display_no(floor_row: Dict[str, Any]) -> int:
    try:
        return int(floor_row.get("floor_number") or floor_row.get("floor_no") or 1)
    except (TypeError, ValueError):
        return 1


def _floor_code_suffix(floor_no: int) -> str:
    return f"L{floor_no:02d}"


def _hub_id_for_floor(rooms_on_floor: List[Dict[str, Any]]) -> Optional[str]:
    for r in rooms_on_floor:
        rid = str(r.get("id") or "")
        if rid.endswith("_circulation_01") and rid not in LANDMARK_ROOM_IDS:
            return rid
    for r in rooms_on_floor:
        rid = str(r.get("id") or "")
        if rid in LANDMARK_ROOM_IDS or rid in _NOT_FLOOR_HUB_IDS:
            continue
        if r.get("room_type") == "circulation" or "space:circulation" in (r.get("tags") or []):
            return rid
    return None


def _make_circulation_room(
    floor_row: Dict[str, Any],
    building_row: Dict[str, Any],
    *,
    seq: int = 1,
) -> Dict[str, Any]:
    fid = str(floor_row["id"])
    bcode = str(building_row.get("building_code") or "X").strip().upper()
    bname = str(building_row.get("building_name") or building_row.get("display_name") or bcode)
    floor_no = _floor_display_no(floor_row)
    floor_name = str(floor_row.get("floor_name") or floor_row.get("display_name") or f"第{floor_no}层")
    uns_prefix = str(floor_row.get("uns") or "").strip()
    layer = f"{bcode}{_floor_code_suffix(floor_no)}"
    room_code = f"{layer}COR{seq:02d}"
    uns = f"{uns_prefix}/{room_code}" if uns_prefix else room_code
    rid = f"{fid}_circulation_{seq:02d}"

    ftags = [str(t).strip().lower() for t in (floor_row.get("tags") or []) if str(t).strip()]
    base_tags = [t for t in ftags if not t.startswith("layer_role:")]
    for extra in ("space:circulation", "zone:public"):
        if extra not in base_tags:
            base_tags.append(extra)

    return {
        "id": rid,
        "world_id": "hicampus",
        "floor_id": fid,
        "type_code": "room",
        "display_name": f"{bname} · {floor_name} 交通核 {seq}",
        "room_name": f"{bname} · {floor_name} 交通核 {seq}",
        "room_name_en": f"Circulation Core {room_code}",
        "room_type": "circulation",
        "room_code": room_code,
        "uns": uns,
        "room_short_description": "电梯厅与楼梯间前室。",
        "room_description": "连接垂直交通与走廊；导向标识指向防火分区与疏散楼梯。",
        "room_ambiance": "电梯到达提示音与脚步声。",
        "room_floor": floor_no,
        "room_building": bname,
        "room_campus": "hicampus",
        "tags": base_tags,
    }


def _star_edges(hub: str, satellites: List[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    sats = sorted(satellites)
    if not sats:
        return out

    used_from_hub: Dict[str, str] = {}

    def add_pair(src: str, tgt: str, d_fwd: str) -> None:
        out.extend(_connect_pair(src, tgt, d_fwd))

    n = len(sats)
    for i in range(min(n, 8)):
        d = DIR_ORDER[i % len(DIR_ORDER)]
        while d in used_from_hub.values():
            # avoid duplicate direction from hub (shouldn't happen for i<8)
            d = DIR_ORDER[(DIR_ORDER.index(d) + 1) % len(DIR_ORDER)]
        used_from_hub[sats[i]] = d
        add_pair(hub, sats[i], d)

    if n <= 8:
        return out

    chain_fwd = "north"
    chain_rev = "south"
    prev = sats[7]
    for j in range(8, n):
        cur = sats[j]
        add_pair(prev, cur, chain_fwd)
        prev = cur
        chain_fwd, chain_rev = chain_rev, chain_fwd

    return out


def _circulation_items(
    circ_room: Dict[str, Any],
    floor_row: Dict[str, Any],
    building_row: Dict[str, Any],
) -> List[Dict[str, Any]]:
    room_id = str(circ_room["id"])
    base = str(circ_room.get("display_name") or circ_room.get("room_name") or room_id)
    fid = str(floor_row["id"])
    bcode = str(building_row.get("building_code") or "F1").strip().upper()
    floor_no = _floor_display_no(floor_row)
    uns_f = str(floor_row.get("uns") or "")
    layer_role = next((t.split(":", 1)[1] for t in (floor_row.get("tags") or []) if str(t).startswith("layer_role:")), "standard")
    layer_lane = next((t.split(":", 1)[1] for t in (floor_row.get("tags") or []) if str(t).startswith("layer:") and not str(t).startswith("layer_role:")), "standard")

    placement = {
        "floor_id": fid,
        "floor_no": floor_no,
        "building_id": str(floor_row.get("building_id") or ""),
        "building_code": bcode,
        "building_type": str(building_row.get("building_type") or "administrative"),
        "layer_role": layer_role,
        "layer": layer_lane,
        "floor_uns": uns_f,
    }

    def item_row(suffix: str, type_code: str, display_suffix: str, attrs: Dict[str, Any], tags: List[str]) -> Dict[str, Any]:
        iid = f"{room_id}_{suffix}"
        return {
            "id": iid,
            "world_id": "hicampus",
            "type_code": type_code,
            "entity_kind": "item",
            "display_name": f"{display_suffix}",
            "location_ref": room_id,
            "attributes": attrs,
            "presentation_domains": ["room"],
            "access_locks": {"view": "all()", "interact": "all()"},
            "tags": tags,
            "source_ref": "entities/items.yaml",
        }

    lighting_attrs = {
        "item_kind": "device",
        "device_role": "lighting",
        "controllable": True,
        "status": "on",
        "lighting": {"brightness_pct": 78, "color_temp_k": 4000, "scene": "transit"},
        "telemetry": {"power_w": None},
        "room_list_name": "照明回路",
        "device_id": f"{room_id}_lighting_fixture_01",
        "asset_tag": f"HC-{_short_hash(room_id + 'lt')[:8].upper()}",
        "placement": dict(placement),
    }
    lounge_attrs = {
        "item_kind": "furniture",
        "furniture_role": "lounge",
        "pieces": {"sofa_count": 2, "chair_count": 4, "table_count": 1},
        "room_list_name": "沙发与等候座",
        "device_id": f"{room_id}_lounge_furniture_01",
        "asset_tag": f"HC-{_short_hash(room_id + 'lg')[:8].upper()}",
        "placement": dict(placement),
    }
    wifi_attrs = {
        "item_kind": "device",
        "device_role": "wifi_ap",
        "controllable": True,
        "status": "on",
        "network": {
            "mode": "ap",
            "bands": ["2.4g", "5g"],
            "ssid": f"HiCampus-{bcode}-L{floor_no:02d}",
            "encryption": "wpa2",
            "ip_mode": "dhcp",
            "vlan_hint": 100 + (int(_short_hash(room_id + "vlan")[:4], 16) % 80),
        },
        "telemetry": {"rssi_dbm": None, "clients": 0, "uplink_mbps": None},
        "room_list_name": "无线接入点",
        "device_id": f"{room_id}_wifi_ap_01",
        "asset_tag": f"HC-{_short_hash(room_id + 'wf')[:8].upper()}",
        "placement": dict(placement),
    }

    return [
        item_row(
            "lighting_fixture_01",
            "lighting_fixture",
            f"{base} · 照明回路",
            lighting_attrs,
            ["item", "device", "controllable", "lighting"],
        ),
        item_row(
            "lounge_furniture_01",
            "lounge_furniture",
            f"{base} · 沙发与等候座",
            lounge_attrs,
            ["item", "furniture", "lounge"],
        ),
        item_row(
            "wifi_ap_01",
            "network_access_point",
            f"{base} · 无线接入点",
            wifi_attrs,
            ["item", "device", "controllable", "network"],
        ),
    ]


def generate_topology(
    *,
    data_root: Path = _DATA_ROOT,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Returns (new_circulation_rooms, new_connects_to, new_items)."""
    rooms_doc = _load_yaml(data_root / "rooms.yaml")
    floors_doc = _load_yaml(data_root / "floors.yaml")
    bdoc = _load_yaml(data_root / "buildings.yaml")
    rooms: List[Dict[str, Any]] = list(rooms_doc.get("rooms") or [])
    floors: List[Dict[str, Any]] = list(floors_doc.get("floors") or [])
    buildings = {str(b["id"]): b for b in (bdoc.get("buildings") or []) if b.get("id")}

    by_floor: Dict[str, List[Dict[str, Any]]] = {}
    for r in rooms:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        fid = str(r.get("floor_id") or "")
        if not fid:
            continue
        by_floor.setdefault(fid, []).append(r)

    existing_ids = {str(r["id"]) for r in rooms}
    new_rooms: List[Dict[str, Any]] = []
    new_items: List[Dict[str, Any]] = []
    connects: List[Dict[str, Any]] = []

    floor_by_id = {str(f["id"]): f for f in floors if f.get("id")}

    for floor_row in sorted(floors, key=lambda f: (str(f.get("building_id")), _floor_display_no(f))):
        fid = str(floor_row.get("id") or "")
        if not fid:
            continue
        on_floor = by_floor.setdefault(fid, [])
        bid = str(floor_row.get("building_id") or "")
        building_row = buildings.get(bid) or {}

        hub = _hub_id_for_floor(on_floor)
        if not hub:
            nr = _make_circulation_room(floor_row, building_row, seq=1)
            hub = str(nr["id"])
            if hub not in existing_ids:
                new_rooms.append(nr)
                existing_ids.add(hub)
                on_floor.append(nr)
                new_items.extend(_circulation_items(nr, floor_row, building_row))

        satellites = [
            str(r["id"])
            for r in on_floor
            if str(r["id"]) != hub and str(r["id"]) not in LANDMARK_ROOM_IDS
        ]

        if fid == "hicampus_f1_01f":
            # 首层：广场/闸机/连桥保留手工边；仅补交通核↔配电间。
            # Use explicit source room to avoid accidental hub drift attaching electrical to hicampus_bridge.
            f1_hub_id = "hicampus_f1_01f_circulation_01"
            if f1_hub_id in existing_ids and "hicampus_f1_01f_electrical_01" in existing_ids:
                connects.extend(_connect_pair(f1_hub_id, "hicampus_f1_01f_electrical_01", "east"))
        else:
            connects.extend(_star_edges(hub, satellites))

    # Campus/building interconnects (entry hubs only).
    # We connect building 1F circulation cores to make the campus graph walkable from the main spine.
    #
    # Spine is preserved manually: gate↔bridge↔plaza↔F1 L01 circulation.
    # Here we generate additional edges:
    # - F1 ↔ F2 (west/east)
    # - F1 ↔ F3 (east/west)
    # - F2 ↔ F4 (south/north)
    # - F3 ↔ F5 (south/north)
    # - F1 ↔ F6 (north/south)
    def hub_for_building_01f(building_id: str) -> Optional[str]:
        b_floors = [f for f in floors if str(f.get("building_id") or "") == building_id]
        if not b_floors:
            return None
        f01 = sorted(b_floors, key=_floor_display_no)[0]
        fid = str(f01.get("id") or "")
        if not fid:
            return None
        on_floor = by_floor.get(fid, [])
        return _hub_id_for_floor(on_floor)

    f1_hub = hub_for_building_01f("hicampus_f1")
    f2_hub = hub_for_building_01f("hicampus_f2")
    f3_hub = hub_for_building_01f("hicampus_f3")
    f4_hub = hub_for_building_01f("hicampus_f4")
    f5_hub = hub_for_building_01f("hicampus_f5")
    f6_hub = hub_for_building_01f("hicampus_f6")

    if f1_hub and f2_hub:
        connects.extend(_connect_pair(f1_hub, f2_hub, "northwest"))
    if f1_hub and f3_hub:
        # Avoid colliding with floor-internal star edges on F3 hub (west/east/south often occupied).
        connects.extend(_connect_pair(f1_hub, f3_hub, "northeast"))
    if f2_hub and f4_hub:
        connects.extend(_connect_pair(f2_hub, f4_hub, "northwest"))
    if f3_hub and f5_hub:
        # Use diagonal pair to avoid collision with F3/F5 internal south/north exits.
        connects.extend(_connect_pair(f3_hub, f5_hub, "southeast"))
    if f1_hub and f6_hub:
        connects.extend(_connect_pair(f1_hub, f6_hub, "southeast"))

    # Vertical chains per building
    by_building_floors: Dict[str, List[Dict[str, Any]]] = {}
    for f in floors:
        bid = str(f.get("building_id") or "")
        if bid:
            by_building_floors.setdefault(bid, []).append(f)

    for bid, flist in by_building_floors.items():
        flist = sorted(flist, key=_floor_display_no)
        hubs: List[str] = []
        for fr in flist:
            fid = str(fr["id"])
            on_floor = by_floor.get(fid, [])
            h = _hub_id_for_floor(on_floor)
            if h:
                hubs.append(h)
        for i in range(len(hubs) - 1):
            lo, hi = hubs[i], hubs[i + 1]
            connects.append(
                {
                    "id": _rel_topo_id(lo, hi, "up"),
                    "rel_type_code": "connects_to",
                    "source_id": lo,
                    "target_id": hi,
                    "directed": True,
                    "attributes": {"direction": "up", "topology_auto": True},
                }
            )
            connects.append(
                {
                    "id": _rel_topo_id(hi, lo, "down"),
                    "rel_type_code": "connects_to",
                    "source_id": hi,
                    "target_id": lo,
                    "directed": True,
                    "attributes": {"direction": "down", "topology_auto": True},
                }
            )

    return new_rooms, connects, new_items


def merge_rooms(existing: List[Dict[str, Any]], additions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = {str(r["id"]) for r in existing if r.get("id")}
    out = list(existing)
    for r in additions:
        rid = str(r.get("id") or "")
        if rid and rid not in seen:
            seen.add(rid)
            out.append(r)
    return out


def merge_items(existing: List[Dict[str, Any]], additions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = {str(r["id"]) for r in existing if r.get("id")}
    out = list(existing)
    for r in additions:
        rid = str(r.get("id") or "")
        if rid and rid not in seen:
            seen.add(rid)
            out.append(r)
    return out


def write_relationships(data_root: Path, new_connects: List[Dict[str, Any]]) -> None:
    path = data_root / "relationships.yaml"
    doc = _load_yaml(path)
    rels = list(doc.get("relationships") or [])
    preserved = [r for r in rels if r.get("id") in PRESERVE_CONNECT_IDS]
    other = [r for r in rels if r.get("rel_type_code") != "connects_to"]
    merged = preserved + new_connects + other
    path.write_text(
        yaml.safe_dump({"relationships": merged}, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def write_rooms(data_root: Path, rooms: List[Dict[str, Any]]) -> None:
    path = data_root / "rooms.yaml"
    path.write_text(
        yaml.safe_dump({"rooms": rooms}, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def write_items(data_root: Path, items: List[Dict[str, Any]]) -> None:
    path = data_root / "entities" / "items.yaml"
    path.write_text(
        yaml.safe_dump({"items": items}, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="HiCampus topology connects_to + circulation rooms")
    p.add_argument("--data-root", type=Path, default=_DATA_ROOT)
    p.add_argument("--write", action="store_true")
    args = p.parse_args(argv)

    new_rooms, connects, new_items = generate_topology(data_root=args.data_root)
    rooms_doc = _load_yaml(args.data_root / "rooms.yaml")
    existing_rooms = list(rooms_doc.get("rooms") or [])
    merged_rooms = merge_rooms(existing_rooms, new_rooms)

    items_doc = _load_yaml(args.data_root / "entities" / "items.yaml")
    existing_items = list(items_doc.get("items") or [])
    merged_items = merge_items(existing_items, new_items)

    print(
        f"new_circulation_rooms={len(new_rooms)} connects_to={len(connects)} new_items={len(new_items)} "
        f"rooms_total={len(merged_rooms)} items_total={len(merged_items)}"
    )
    if not args.write:
        return 0

    write_rooms(args.data_root, merged_rooms)
    write_relationships(args.data_root, connects)
    write_items(args.data_root, merged_items)
    print(f"Wrote rooms, relationships, items under {args.data_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
