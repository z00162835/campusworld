"""
Generate HiCampus entities/items.yaml from rooms.yaml + item_templates + item_placement_rules.
Preserves hand-authored item rows by id (gate terminal, plaza bench).
"""

from __future__ import annotations

import argparse
import copy
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

_PACKAGE_DIR = Path(__file__).resolve().parent
_DATA_ROOT = _PACKAGE_DIR.parent / "data"

_PRESERVED_ITEM_IDS = frozenset(
    {
        "hicampus_device_gate_terminal_01",
        "hicampus_furniture_bench_01",
    }
)


def _load_yaml(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(path)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _room_tags(room: Dict[str, Any]) -> Set[str]:
    return {str(t).strip().lower() for t in (room.get("tags") or []) if str(t).strip()}


def _floor_tags(floor: Dict[str, Any]) -> Set[str]:
    return {str(t).strip().lower() for t in (floor.get("tags") or []) if str(t).strip()}


def _tag_prefix_value(tags: Set[str], prefix: str) -> Optional[str]:
    for t in tags:
        if t.startswith(prefix):
            return t.split(":", 1)[1].strip()
    return None


def _placement_for_room(
    room: Dict[str, Any],
    floor_by_id: Dict[str, Dict[str, Any]],
    building_by_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Resolve authoritative building/floor context from spatial package (rooms -> floors -> buildings)."""
    fid = str(room.get("floor_id") or "").strip()
    floor = floor_by_id.get(fid) or {}
    ftags = _floor_tags(floor) if floor else set()
    layer_role = _tag_prefix_value(ftags, "layer_role:") or "unknown"
    layer_lane = _tag_prefix_value(ftags, "layer:") or _tag_prefix_value(_room_tags(room), "layer:") or ""

    bid = str(floor.get("building_id") or "").strip()
    building = building_by_id.get(bid) or {}

    bcode = str(building.get("building_code") or "").strip().upper()
    if not bcode:
        bcode = next(
            (t.upper() for t in _room_tags(room) if len(t) == 2 and t[0] == "f" and t[1].isdigit()),
            "UNK",
        )

    floor_no = floor.get("floor_number")
    if floor_no is None:
        floor_no = floor.get("floor_no")
    if floor_no is None:
        floor_no = room.get("room_floor")
    try:
        floor_no_i = int(floor_no) if floor_no is not None else 1
    except (TypeError, ValueError):
        floor_no_i = 1

    btype = str(building.get("building_type") or "").strip().lower()

    return {
        "floor_id": fid or None,
        "floor_no": floor_no_i,
        "building_id": bid or None,
        "building_code": bcode,
        "building_type": btype,
        "layer_role": layer_role,
        "layer": layer_lane,
        "floor_uns": str(floor.get("uns") or "").strip() or None,
    }


def _rule_match(match: Dict[str, Any], tags: Set[str]) -> bool:
    ex = match.get("exclude_tags_any") or []
    if tags.intersection({str(x).lower() for x in ex}):
        return False
    req_all = match.get("require_tags_all") or []
    if req_all:
        need = {str(x).lower() for x in req_all}
        if not need.issubset(tags):
            return False
    req_any = match.get("require_tags_any") or []
    if req_any:
        if not tags.intersection({str(x).lower() for x in req_any}):
            return False
    return True


def _build_item_row(
    *,
    template_key: str,
    template: Dict[str, Any],
    room: Dict[str, Any],
    seq: int,
    placement: Dict[str, Any],
) -> Dict[str, Any]:
    rid = str(room["id"])
    rname = str(room.get("display_name") or room.get("room_name") or rid)
    tags = _room_tags(room)
    bcode = str(placement.get("building_code") or "UNK").upper()
    floor_no = int(placement.get("floor_no") or 1)
    layer_role = str(placement.get("layer_role") or "unknown")
    layer = str(placement.get("layer") or "") or next(
        (t.split(":", 1)[1] for t in tags if t.startswith("layer:")),
        "",
    )
    ctx = {
        "room_name": rname,
        "room_id": rid,
        "building_code": bcode,
        "floor_no": floor_no,
        "layer": layer or "standard",
        "layer_role": layer_role,
    }
    name_tpl = str(template.get("display_name_tpl") or "{room_name}")
    display_name = name_tpl.format(**ctx)
    iid = f"{rid}_{template_key}_{seq:02d}"

    attrs = copy.deepcopy(template.get("attributes") or {})
    if not isinstance(attrs, dict):
        attrs = {}

    if " · " in display_name:
        attrs.setdefault("room_list_name", display_name.rsplit(" · ", 1)[-1].strip())

    # Deterministic per-item identity helpers for operations/telemetry stubs.
    h = hashlib.sha1(iid.encode("utf-8")).hexdigest()
    attrs.setdefault("device_id", iid)
    attrs.setdefault("asset_tag", f"HC-{h[:8].upper()}")
    attrs["placement"] = {k: v for k, v in placement.items() if v is not None}

    # Room-aware attribute enrichment (keep templates as baseline; override selectively).
    device_role = str(attrs.get("device_role") or "")
    if device_role == "wifi_ap":
        net = attrs.setdefault("network", {})
        if isinstance(net, dict):
            net["ssid"] = f"HiCampus-{bcode}-L{floor_no:02d}"
            net.setdefault("bands", ["2.4g", "5g"])
            if "space:meeting" in tags and "6g" not in net.get("bands", []):
                net["bands"] = list(net.get("bands") or []) + ["6g"]
            if layer_role in {"lobby", "training_entry", "canteen"}:
                net.setdefault("guest_ssid", f"HiCampus-Guest-{bcode}")
            net.setdefault("encryption", "wpa2")
            net.setdefault("ip_mode", "dhcp")
            net.setdefault("vlan_hint", 100 + (int(h[:4], 16) % 50))
        tele = attrs.setdefault("telemetry", {})
        if isinstance(tele, dict):
            tele.setdefault("clients", 0)
    elif device_role == "lighting":
        lighting = attrs.setdefault("lighting", {})
        if isinstance(lighting, dict):
            if "space:meeting" in tags:
                lighting.setdefault("scene", "presentation")
                lighting.setdefault("color_temp_k", 5000)
                lighting.setdefault("brightness_pct", 70)
            elif layer_role in {"canteen"} or "space:lounge" in tags:
                lighting.setdefault("scene", "dining_warm")
                lighting.setdefault("color_temp_k", 3000)
                lighting.setdefault("brightness_pct", 65)
            elif layer_role in {"lobby", "training_entry"} or "layer:public" in tags:
                lighting.setdefault("scene", "arrival")
                lighting.setdefault("color_temp_k", 4500)
                lighting.setdefault("brightness_pct", 85)
            elif "space:circulation" in tags or layer_role in {"meeting_heavy"}:
                lighting.setdefault("scene", "transit")
                lighting.setdefault("color_temp_k", 4000)
                lighting.setdefault("brightness_pct", 78)
            elif layer_role in {"executive"}:
                lighting.setdefault("scene", "executive_soft")
                lighting.setdefault("color_temp_k", 3500)
                lighting.setdefault("brightness_pct", 72)
            else:
                lighting.setdefault("scene", "work")
                lighting.setdefault("color_temp_k", 4000)
                lighting.setdefault("brightness_pct", 80)
        tele = attrs.setdefault("telemetry", {})
        if isinstance(tele, dict):
            tele.setdefault("power_w", None)
    elif device_role == "display":
        av = attrs.setdefault("av", {})
        if isinstance(av, dict):
            if "space:expo" in tags or layer_role in {"lobby"}:
                av.setdefault("resolution", "8k")
                av.setdefault("volume_pct", 18)
            elif "space:classroom" in tags and str(placement.get("building_type") or "") == "academic":
                av.setdefault("resolution", "4k")
                av.setdefault("volume_pct", 35)
                av.setdefault("mode", "education")
            elif layer_role in {"executive"} and "space:meeting" in tags:
                av.setdefault("resolution", "4k")
                av.setdefault("volume_pct", 25)
                av.setdefault("mode", "boardroom")
            elif layer_role in {"meeting_heavy"} and "space:meeting" in tags:
                av.setdefault("resolution", "4k")
                av.setdefault("brightness_nit", 450)
                av.setdefault("volume_pct", 28)
            else:
                av.setdefault("resolution", "4k")
                av.setdefault("volume_pct", 30)
            av.setdefault("inputs", ["hdmi", "wireless_cast"])
        tele = attrs.setdefault("telemetry", {})
        if isinstance(tele, dict):
            tele.setdefault("temperature_c", None)

    # Furniture enrichment driven by room tags.
    if str(attrs.get("item_kind") or "") == "furniture":
        role = str(attrs.get("furniture_role") or "")
        if role == "conference_seating":
            if layer_role in {"meeting_heavy"}:
                attrs["seat_count"] = 12
            elif layer_role in {"executive"}:
                attrs["seat_count"] = 10
            else:
                attrs.setdefault("seat_count", 8)
            if layer_role in {"executive"}:
                attrs["layout"] = "boardroom"
            elif layer_role in {"meeting_heavy"}:
                attrs["layout"] = "u_shape"
        elif role == "lounge":
            pieces = attrs.setdefault("pieces", {})
            if isinstance(pieces, dict):
                if layer_role in {"lobby", "training_entry"} or "layer:public" in tags or layer in {"entry", "public"}:
                    pieces.setdefault("sofa_count", 3)
                    pieces.setdefault("chair_count", 6)
                else:
                    pieces.setdefault("sofa_count", 2)
                    pieces.setdefault("chair_count", 4)

    row: Dict[str, Any] = {
        "id": iid,
        "world_id": "hicampus",
        "type_code": template["type_code"],
        "entity_kind": "item",
        "display_name": display_name,
        "location_ref": rid,
        "attributes": attrs,
        "presentation_domains": list(template.get("presentation_domains") or ["room"]),
        "access_locks": copy.deepcopy(template.get("access_locks") or {"view": "all()", "interact": "all()"}),
        "tags": [str(t) for t in (template.get("tags") or [])],
        "source_ref": "entities/items.yaml",
    }
    return row


def generate_items(
    *,
    data_root: Optional[Path] = None,
    package_dir: Path = _PACKAGE_DIR,
) -> List[Dict[str, Any]]:
    data_root = data_root or _DATA_ROOT
    tmpl_doc = _load_yaml(package_dir / "item_templates.yaml")
    rules_doc = _load_yaml(package_dir / "item_placement_rules.yaml")
    templates: Dict[str, Any] = tmpl_doc.get("templates") or {}
    device_rules: List[Dict[str, Any]] = list(rules_doc.get("device_rules") or [])
    furniture_rules: List[Dict[str, Any]] = list(rules_doc.get("furniture_rules") or [])

    rooms_doc = _load_yaml(data_root / "rooms.yaml")
    rooms: List[Dict[str, Any]] = [r for r in (rooms_doc.get("rooms") or []) if isinstance(r, dict) and r.get("id")]

    floor_by_id: Dict[str, Dict[str, Any]] = {}
    if (data_root / "floors.yaml").is_file():
        for frow in _load_yaml(data_root / "floors.yaml").get("floors") or []:
            if isinstance(frow, dict) and frow.get("id"):
                floor_by_id[str(frow["id"])] = frow
    building_by_id: Dict[str, Dict[str, Any]] = {}
    if (data_root / "buildings.yaml").is_file():
        for brow in _load_yaml(data_root / "buildings.yaml").get("buildings") or []:
            if isinstance(brow, dict) and brow.get("id"):
                building_by_id[str(brow["id"])] = brow

    generated: List[Dict[str, Any]] = []
    for room in rooms:
        tags = _room_tags(room)
        per_key_seq: Dict[str, int] = {}
        placement = _placement_for_room(room, floor_by_id, building_by_id)

        for dr in device_rules:
            if not _rule_match(dr.get("match") or {}, tags):
                continue
            for spec in dr.get("add_templates") or []:
                tid = str(spec.get("template_id") or "")
                if not tid or tid not in templates:
                    raise ValueError(f"unknown template_id {tid!r} in device rule {dr.get('id')!r}")
                n = int(spec.get("count", 1))
                tdef = templates[tid]
                for _ in range(n):
                    per_key_seq[tid] = per_key_seq.get(tid, 0) + 1
                    generated.append(
                        _build_item_row(
                            template_key=tid,
                            template=tdef,
                            room=room,
                            seq=per_key_seq[tid],
                            placement=placement,
                        )
                    )

        for fr in furniture_rules:
            if not _rule_match(fr.get("match") or {}, tags):
                continue
            for spec in fr.get("add_templates") or []:
                tid = str(spec.get("template_id") or "")
                if not tid or tid not in templates:
                    raise ValueError(f"unknown template_id {tid!r} in furniture rule {fr.get('id')!r}")
                n = int(spec.get("count", 1))
                tdef = templates[tid]
                for _ in range(n):
                    per_key_seq[tid] = per_key_seq.get(tid, 0) + 1
                    generated.append(
                        _build_item_row(
                            template_key=tid,
                            template=tdef,
                            room=room,
                            seq=per_key_seq[tid],
                            placement=placement,
                        )
                    )
            break

    generated.sort(key=lambda r: (str(r.get("location_ref", "")), r["id"]))
    return generated


def load_preserved_items(data_root: Path) -> List[Dict[str, Any]]:
    path = data_root / "entities" / "items.yaml"
    doc = _load_yaml(path)
    out: List[Dict[str, Any]] = []
    for row in doc.get("items") or []:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id", ""))
        if rid in _PRESERVED_ITEM_IDS:
            copy_row = copy.deepcopy(row)
            attrs = copy_row.get("attributes")
            if not isinstance(attrs, dict):
                attrs = {}
                copy_row["attributes"] = attrs
            attrs.setdefault("device_id", rid)
            attrs.setdefault("asset_tag", f"HC-{hashlib.sha1(rid.encode('utf-8')).hexdigest()[:8].upper()}")
            out.append(copy_row)
    return out


def merge_items(preserved: List[Dict[str, Any]], generated: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Set[str] = set()
    merged: List[Dict[str, Any]] = []
    for row in preserved:
        iid = str(row["id"])
        if iid in seen:
            continue
        seen.add(iid)
        merged.append(row)
    for row in generated:
        iid = str(row["id"])
        if iid in seen:
            continue
        seen.add(iid)
        merged.append(row)
    merged.sort(key=lambda r: (str(r.get("location_ref", "")), r["id"]))
    return merged


def write_yaml(path: Path, key: str, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump({key: rows}, allow_unicode=True, sort_keys=False, default_flow_style=False)
    path.write_text(text, encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="HiCampus entity items.yaml generator")
    p.add_argument("--data-root", type=Path, default=_DATA_ROOT)
    p.add_argument("--package-dir", type=Path, default=_PACKAGE_DIR)
    p.add_argument("--write", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    gen = generate_items(data_root=args.data_root, package_dir=args.package_dir)
    preserved = load_preserved_items(args.data_root)
    merged = merge_items(preserved, gen)
    if args.dry_run or not args.write:
        print(f"preserved={len(preserved)} generated={len(gen)} merged={len(merged)}")
        return 0
    out = args.data_root / "entities" / "items.yaml"
    write_yaml(out, "items", merged)
    print(f"Wrote items={len(merged)} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
