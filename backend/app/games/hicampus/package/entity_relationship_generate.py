"""
Generate HiCampus relationships.yaml additions from entities.

Phase 3:
- Ensure each item and npc has a located_in relationship to its location_ref room.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

_PACKAGE_DIR = Path(__file__).resolve().parent
_DATA_ROOT = _PACKAGE_DIR.parent / "data"


def _load_yaml(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(path)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _short_hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]


def generate_item_located_in_relationships(*, data_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    data_root = data_root or _DATA_ROOT
    items_doc = _load_yaml(data_root / "entities" / "items.yaml")
    items = items_doc.get("items") or []
    out: List[Dict[str, Any]] = []
    for row in items:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        iid = str(row["id"])
        loc = row.get("location_ref")
        if not loc:
            continue
        rid = str(loc)
        rel_id = f"rel_item_located_in_{_short_hash(iid)}"
        out.append(
            {
                "id": rel_id,
                "rel_type_code": "located_in",
                "source_id": iid,
                "target_id": rid,
                "directed": True,
                "attributes": {"source_kind": "item"},
            }
        )
    return out


def generate_npc_located_in_relationships(*, data_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    data_root = data_root or _DATA_ROOT
    npcs_doc = _load_yaml(data_root / "entities" / "npcs.yaml")
    npcs = npcs_doc.get("npcs") or []
    out: List[Dict[str, Any]] = []
    for row in npcs:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        nid = str(row["id"])
        loc = row.get("location_ref")
        if not loc:
            continue
        rid = str(loc)
        rel_id = f"rel_npc_located_in_{_short_hash(nid)}"
        out.append(
            {
                "id": rel_id,
                "rel_type_code": "located_in",
                "source_id": nid,
                "target_id": rid,
                "directed": True,
                "attributes": {"source_kind": "npc"},
            }
        )
    return out


def merge_relationships(existing: List[Dict[str, Any]], additions: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """
    Merge by (rel_type_code, source_id, target_id) identity; keep existing rows.
    Returns (merged, added_count).
    """
    seen_keys: Set[Tuple[str, str, str]] = set()
    merged: List[Dict[str, Any]] = []
    for r in existing:
        if not isinstance(r, dict):
            continue
        rtc = str(r.get("rel_type_code") or "")
        src = str(r.get("source_id") or "")
        tgt = str(r.get("target_id") or "")
        if rtc and src and tgt:
            seen_keys.add((rtc, src, tgt))
        merged.append(r)

    added = 0
    for r in additions:
        rtc = str(r.get("rel_type_code") or "")
        src = str(r.get("source_id") or "")
        tgt = str(r.get("target_id") or "")
        key = (rtc, src, tgt)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        merged.append(r)
        added += 1

    return merged, added


def write_yaml(path: Path, key: str, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump({key: rows}, allow_unicode=True, sort_keys=False, default_flow_style=False)
    path.write_text(text, encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="HiCampus relationships.yaml generator (Phase 3)")
    p.add_argument("--data-root", type=Path, default=_DATA_ROOT)
    p.add_argument("--write", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    rel_path = args.data_root / "relationships.yaml"
    rels_doc = _load_yaml(rel_path)
    existing = list(rels_doc.get("relationships") or [])
    additions = []
    additions.extend(generate_item_located_in_relationships(data_root=args.data_root))
    additions.extend(generate_npc_located_in_relationships(data_root=args.data_root))
    merged, added = merge_relationships(existing, additions)

    if args.dry_run or not args.write:
        print(f"existing={len(existing)} additions={len(additions)} added={added} merged={len(merged)}")
        return 0

    write_yaml(rel_path, "relationships", merged)
    print(f"Wrote relationships={len(merged)} (+{added}) -> {rel_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

