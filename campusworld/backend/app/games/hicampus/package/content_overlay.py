"""
F07: apply spatial description attributes to existing graph nodes (package_node_id + world_id).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.game_engine.subgraph_boundary import node_world_id
from app.models.graph import Node

from .content_merge import collect_spatial_completeness_gaps
from .validator import validate_data_package as _validate_full_package

_SPATIAL_SKIP = frozenset({"id", "type_code", "display_name", "tags"})


def _row_to_attrs(row: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in row.items() if k not in _SPATIAL_SKIP}


def _find_node_by_pkg(session: Session, world_id: str, package_node_id: str) -> Optional[Node]:
    wid = str(world_id).strip().lower()
    nodes = (
        session.query(Node)
        .filter(
            Node.attributes["package_node_id"].astext == str(package_node_id),
            Node.is_active == True,  # noqa: E712
        )
        .all()
    )
    for n in nodes:
        if node_world_id(n) == wid:
            return n
    return None


def build_expected_spatial_state(data_root: Path) -> Dict[str, Any]:
    """Validate package and return spatial dict (sidecar merge + normalization already applied)."""
    return _validate_full_package(data_root)["spatial"]


def diff_spatial_vs_db(session: Session, world_id: str, data_root: Path) -> Dict[str, Any]:
    """Compare package spatial rows with DB node attributes (only keys present in package row)."""
    spatial = build_expected_spatial_state(data_root)
    diffs: List[Dict[str, Any]] = []
    wid = str(world_id).strip().lower()

    def _scan(rows: List[Dict[str, Any]], kind: str) -> None:
        for row in rows:
            if not isinstance(row, dict) or not row.get("id"):
                continue
            pkg_id = str(row["id"])
            expected = _row_to_attrs(row)
            node = _find_node_by_pkg(session, wid, pkg_id)
            if not node:
                diffs.append({"kind": kind, "package_node_id": pkg_id, "issue": "node_not_found"})
                continue
            attrs = dict(node.attributes or {})
            field_diffs: Dict[str, Any] = {}
            for k, v in expected.items():
                if attrs.get(k) != v:
                    field_diffs[k] = {"db": attrs.get(k), "package": v}
            if field_diffs:
                diffs.append(
                    {
                        "kind": kind,
                        "package_node_id": pkg_id,
                        "node_id": int(node.id),
                        "fields": field_diffs,
                    }
                )

    _scan(spatial.get("buildings") or [], "building")
    _scan(spatial.get("floors") or [], "floor")
    _scan(spatial.get("rooms") or [], "room")
    return {"world_id": wid, "diff_count": len(diffs), "diffs": diffs}


def apply_spatial_content_overlay(
    session: Session,
    world_id: str,
    data_root: Path,
    *,
    dry_run: bool = False,
    write_revision_snapshot: bool = True,
) -> Dict[str, Any]:
    """
    Merge description fields from package into existing nodes. Does not create nodes.
    When write_revision_snapshot and not dry_run, writes JSON under data_root/content/revisions/.
    """
    spatial = build_expected_spatial_state(data_root)
    wid = str(world_id).strip().lower()
    applied: List[str] = []
    missing: List[str] = []
    before_snap: Dict[str, Any] = {"world_id": wid, "captured_at": datetime.now(timezone.utc).isoformat(), "nodes": {}}

    def _apply_rows(rows: List[Dict[str, Any]]) -> None:
        for row in rows:
            if not isinstance(row, dict) or not row.get("id"):
                continue
            pkg_id = str(row["id"])
            overlay = _row_to_attrs(row)
            if not overlay:
                continue
            node = _find_node_by_pkg(session, wid, pkg_id)
            if not node:
                missing.append(pkg_id)
                continue
            attrs = dict(node.attributes or {})
            keys: Set[str] = set(overlay.keys())
            before_snap["nodes"][pkg_id] = {k: attrs.get(k) for k in keys if k in attrs or k in overlay}
            for k, v in overlay.items():
                attrs[k] = v
            node.attributes = attrs
            applied.append(pkg_id)

    _apply_rows(spatial.get("buildings") or [])
    _apply_rows(spatial.get("floors") or [])
    _apply_rows(spatial.get("rooms") or [])

    rev_dir = data_root / "content" / "revisions"
    snapshot_path: Optional[str] = None
    if not dry_run and write_revision_snapshot and (applied or missing):
        rev_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        fn = rev_dir / f"{wid}_content_{ts}.json"
        fn.write_text(json.dumps(before_snap, ensure_ascii=False, indent=2), encoding="utf-8")
        snapshot_path = str(fn)

    if not dry_run and applied:
        session.commit()
    elif not dry_run:
        session.rollback()
    else:
        session.rollback()

    return {
        "ok": True,
        "dry_run": dry_run,
        "world_id": wid,
        "applied_node_ids": applied,
        "missing_in_graph": missing,
        "revision_snapshot_path": snapshot_path,
    }


def content_validate_report(data_root: Path, *, required_room_ids: Optional[Set[str]] = None) -> Dict[str, Any]:
    """Full package validate + completeness gap lists (non-throwing summary)."""
    from .validator import _load_l4_baseline

    try:
        payload = _validate_full_package(data_root)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "building_gaps": [], "floor_gaps": [], "room_gaps": []}
    _, req = _load_l4_baseline()
    rooms = required_room_ids if required_room_ids is not None else req
    spatial = payload["spatial"]
    gb, gf, gr = collect_spatial_completeness_gaps(spatial, required_room_ids=rooms)
    return {
        "ok": len(gb) + len(gf) + len(gr) == 0,
        "building_gaps": gb,
        "floor_gaps": gf,
        "room_gaps": gr,
    }
