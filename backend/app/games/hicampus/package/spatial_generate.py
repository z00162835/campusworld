"""
Generate HiCampus floors.yaml + rooms.yaml from baseline_profile + spatial_profiles.yaml.
Deterministic RNG; supports tag include/exclude filter on output.
"""

from __future__ import annotations

import argparse
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

from .spatial_archetypes import ARCHETYPES, merge_tags

_PACKAGE_DIR = Path(__file__).resolve().parent
_DATA_ROOT = _PACKAGE_DIR.parent / "data"
_REQUIRED_ROOMS = frozenset({"hicampus_gate", "hicampus_bridge", "hicampus_plaza"})

_ARCH_ABBR = {
    "office": "OFF",
    "meeting": "MTG",
    "manager": "MGR",
    "restroom": "WCR",
    "electrical": "ELE",
    "monitoring": "SEC",
    "circulation": "COR",
    "pantry": "PAN",
    "canteen_dining": "DIN",
    "kitchen": "KIT",
    "storage": "STO",
    "classroom": "CLS",
    "lab": "LAB",
    "prep_lab": "PRE",
    "expo_hall": "EXP",
    "av_room": "AVC",
    "dorm_unit": "DRM",
    "lounge": "LNG",
}


def _floor_label_cn(n: int) -> str:
    if n == 1:
        return "首层"
    return f"第{n}层"


def _load_yaml(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(path)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_floor_expect(package_dir: Path) -> Dict[str, int]:
    p = package_dir / "baseline_profile.yaml"
    doc = _load_yaml(p)
    fe = doc.get("floor_expect") or {}
    return {str(k): int(v) for k, v in fe.items()}


def load_spatial_profile(package_dir: Path) -> Dict[str, Any]:
    return _load_yaml(package_dir / "spatial_profiles.yaml")


def _template_for_floor(building_code: str, floor_no: int, profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    b = (profile.get("buildings") or {}).get(building_code)
    if not b:
        return None
    for t in b.get("templates") or []:
        lo, hi = int(t["range"][0]), int(t["range"][1])
        if lo <= floor_no <= hi:
            return t
    return None


def _expand_mix(room_mix: Dict[str, Any], rng: random.Random) -> List[str]:
    items: List[str] = []
    for k, v in room_mix.items():
        n = int(v)
        items.extend([str(k)] * n)
    rng.shuffle(items)
    return items


def _filter_by_tags(
    rooms: List[Dict[str, Any]],
    include: Optional[Set[str]],
    exclude: Optional[Set[str]],
    match_all: bool,
) -> List[Dict[str, Any]]:
    if not include and not exclude:
        return rooms
    out: List[Dict[str, Any]] = []
    for r in rooms:
        tags = {str(x).lower() for x in (r.get("tags") or [])}
        if exclude and tags & exclude:
            continue
        if include:
            if match_all:
                if not include.issubset(tags):
                    continue
            else:
                if not (tags & include):
                    continue
        out.append(r)
    return out


def generate_spatial(
    *,
    data_root: Optional[Path] = None,
    package_dir: Path = _PACKAGE_DIR,
    seed: str = "hicampus-spatial-v1",
    include_tags: Optional[Set[str]] = None,
    exclude_tags: Optional[Set[str]] = None,
    match_all_include: bool = False,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    data_root = data_root or _DATA_ROOT
    floor_expect = load_floor_expect(package_dir)
    profile = load_spatial_profile(package_dir)
    buildings_doc = _load_yaml(data_root / "buildings.yaml")
    buildings = buildings_doc.get("buildings") or []
    by_code = {str(b.get("building_code")): b for b in buildings if b.get("building_code")}

    preserved: List[Dict[str, Any]] = []
    rooms_doc = _load_yaml(data_root / "rooms.yaml")
    for row in rooms_doc.get("rooms") or []:
        rid = str(row.get("id", ""))
        if rid in _REQUIRED_ROOMS:
            copy = dict(row)
            copy.setdefault("tags", [])
            base_tags = ["room", "hicampus", "space:core"]
            if rid == "hicampus_gate":
                base_tags.extend(["landmark", "layer:entry"])
            elif rid == "hicampus_bridge":
                base_tags.extend(["circulation", "layer:connector"])
            else:
                base_tags.extend(["plaza", "layer:public"])
            copy["tags"] = merge_tags([], [], list(copy.get("tags") or []) + base_tags)
            preserved.append(copy)

    floors_out: List[Dict[str, Any]] = []
    rooms_out: List[Dict[str, Any]] = []

    for bcode, n_floors in sorted(floor_expect.items()):
        b = by_code.get(bcode)
        if not b:
            raise ValueError(f"unknown building_code in buildings.yaml: {bcode}")
        bid = str(b["id"])
        bname = str(b.get("building_name") or b.get("display_name") or bcode)
        btags = list(b.get("tags") or [])

        for fn in range(1, n_floors + 1):
            tmpl = _template_for_floor(bcode, fn, profile)
            if not tmpl:
                raise ValueError(f"no spatial profile template for {bcode} floor {fn}")
            floor_tags = [str(x) for x in (tmpl.get("floor_tags") or [])]
            layer_role = str(tmpl.get("layer_role", "default"))
            nn = fn
            fid = f"{bid}_{nn:02d}f"
            floor_code = f"hicampus_{bcode}_L{nn:02d}"
            uns_f = f"hicampus/{bcode}/L{nn:02d}"
            flabel = _floor_label_cn(nn)
            fd_short = f"{bcode} {flabel}，{layer_role}。"
            fd_long = (
                f"{bname}的{flabel}（{layer_role}）。动线与消防分区符合园区标准；"
                f"本层由空间生成器按 profile 生成配套房间。"
            )
            floors_out.append(
                {
                    "id": fid,
                    "world_id": "hicampus",
                    "building_id": bid,
                    "floor_no": nn,
                    "floor_number": nn,
                    "type_code": "building_floor",
                    "display_name": f"{bcode} · {flabel}",
                    "floor_name": flabel,
                    "floor_code": floor_code,
                    "uns": uns_f,
                    "floor_description": fd_long,
                    "floor_short_description": fd_short,
                    "tags": merge_tags(btags, floor_tags, [f"layer_role:{layer_role}"]),
                }
            )

            room_mix = tmpl.get("room_mix") or {}
            if not isinstance(room_mix, dict) or not room_mix:
                continue
            rng = random.Random(f"{seed}|{bid}|{nn}")
            sequence = _expand_mix(room_mix, rng)
            per_arch_seq: Dict[str, int] = {}

            for arche in sequence:
                if arche not in ARCHETYPES:
                    raise ValueError(f"unknown archetype '{arche}' in profile for {bcode} L{nn}")
                per_arch_seq[arche] = per_arch_seq.get(arche, 0) + 1
                seqn = per_arch_seq[arche]
                abbr = _ARCH_ABBR.get(arche, arche[:3].upper())
                room_code = f"{bcode}L{nn:02d}{abbr}{seqn:02d}"
                rid = f"{bid}_{nn:02d}f_{arche}_{seqn:02d}"
                meta = ARCHETYPES[arche]
                ctx = {
                    "building": bname,
                    "floor_label": flabel,
                    "seq": seqn,
                    "code": room_code,
                    "bcode": bcode,
                }
                rname = str(meta["name_tpl"]).format(**ctx)
                rname_en = str(meta["name_en_tpl"]).format(**ctx)
                rtags = merge_tags(btags, floor_tags, list(meta["tags"]))
                rooms_out.append(
                    {
                        "id": rid,
                        "world_id": "hicampus",
                        "floor_id": fid,
                        "type_code": "room",
                        "display_name": rname,
                        "room_name": rname,
                        "room_name_en": rname_en,
                        "room_type": meta["room_type"],
                        "room_code": room_code,
                        "uns": f"hicampus/{bcode}/L{nn:02d}/{room_code}",
                        "room_short_description": str(meta["short_tpl"]).format(**ctx),
                        "room_description": str(meta["desc_tpl"]).format(**ctx),
                        "room_ambiance": str(meta["ambiance_tpl"]).format(**ctx),
                        "room_floor": nn,
                        "room_building": bname,
                        "room_campus": "hicampus",
                        "tags": rtags,
                    }
                )

    gen_filtered = _filter_by_tags(rooms_out, include_tags, exclude_tags, match_all_include)
    merged_rooms = preserved + gen_filtered
    merged_rooms.sort(key=lambda r: (r.get("floor_id", ""), r["id"]))

    return floors_out, merged_rooms


def write_yaml(path: Path, key: str, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump({key: rows}, allow_unicode=True, sort_keys=False, default_flow_style=False)
    path.write_text(text, encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="HiCampus spatial YAML generator")
    p.add_argument("--data-root", type=Path, default=_DATA_ROOT, help="Path to hicampus/data")
    p.add_argument("--package-dir", type=Path, default=_PACKAGE_DIR, help="Path to hicampus/package")
    p.add_argument("--write", action="store_true", help="Write floors.yaml and rooms.yaml")
    p.add_argument("--dry-run", action="store_true", help="Print counts only")
    p.add_argument("--seed", type=str, default="hicampus-spatial-v1")
    p.add_argument("--include-tags", type=str, default="", help="Comma-separated; ANY match unless --match-all")
    p.add_argument("--exclude-tags", type=str, default="", help="Comma-separated; drop if any match")
    p.add_argument("--match-all", action="store_true", help="Require all include-tags on each room")
    p.add_argument(
        "--allow-partial-rooms",
        action="store_true",
        help="Allow --include-tags/--exclude-tags to shrink room list when using --write (default: filters apply only with --dry-run)",
    )
    args = p.parse_args(argv)

    inc = {x.strip().lower() for x in args.include_tags.split(",") if x.strip()}
    exc = {x.strip().lower() for x in args.exclude_tags.split(",") if x.strip()}
    use_filters = bool(inc or exc)
    if args.write and use_filters and not args.allow_partial_rooms:
        inc, exc = set(), set()
    floors, rooms = generate_spatial(
        data_root=args.data_root,
        package_dir=args.package_dir,
        seed=args.seed,
        include_tags=inc or None,
        exclude_tags=exc or None,
        match_all_include=bool(args.match_all),
    )
    if args.dry_run or not args.write:
        print(f"floors={len(floors)} rooms={len(rooms)}")
        return 0
    write_yaml(args.data_root / "floors.yaml", "floors", floors)
    write_yaml(args.data_root / "rooms.yaml", "rooms", rooms)
    print(f"Wrote floors={len(floors)} rooms={len(rooms)} -> {args.data_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
