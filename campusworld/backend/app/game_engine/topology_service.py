"""
Topology validate/repair service for world graph data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid as uuidlib

from app.core.database import db_session_context
from app.models.graph import Node, Relationship, RelationshipType


@dataclass
class TopologyIssue:
    code: str
    message: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": dict(self.details)}


class WorldTopologyService:
    """Validate and repair world topology consistency."""

    _DEFAULT_PROFILE: Dict[str, Any] = {"required_core_rooms": []}
    _HICAMPUS_PROFILE: Dict[str, Any] = {
        "required_core_rooms": ["hicampus_gate", "hicampus_bridge", "hicampus_plaza"]
    }

    def _get_profile(self, world_id: str) -> Dict[str, Any]:
        wid = str(world_id or "").strip().lower()
        if wid == "hicampus":
            return dict(self._HICAMPUS_PROFILE)
        return dict(self._DEFAULT_PROFILE)

    def validate_topology(self, world_id: str) -> Dict[str, Any]:
        issues = self._collect_issues(world_id)
        return {
            "world_id": world_id,
            "ok": len(issues) == 0,
            "issues": [x.to_dict() for x in issues],
            "issue_count": len(issues),
        }

    def repair_topology(self, world_id: str, *, dry_run: bool = True, force: bool = False) -> Dict[str, Any]:
        issues = self._collect_issues(world_id)
        planned = self._build_repair_actions(issues)
        applied = []
        skipped = []
        if dry_run:
            return {
                "world_id": world_id,
                "dry_run": True,
                "force": force,
                "issues": [x.to_dict() for x in issues],
                "issues_count": len(issues),
                "planned_actions": planned,
                "applied_actions": [],
                "skipped_actions": [],
                "ok": len(planned) == 0,
            }

        for action in planned:
            if action.get("action") == "create_reverse_connects_to":
                if not force:
                    skipped.append({**action, "reason": "force_required"})
                    continue
                result = self._apply_create_reverse_connects_to(action)
                if result.get("applied"):
                    applied.append(action)
                else:
                    skipped.append({**action, "reason": result.get("reason", "not_applied")})
            else:
                skipped.append({**action, "reason": "unsupported_action"})

        return {
            "world_id": world_id,
            "dry_run": False,
            "force": force,
            "issues": [x.to_dict() for x in issues],
            "issues_count": len(issues),
            "planned_actions": planned,
            "applied_actions": applied,
            "skipped_actions": skipped,
            "ok": (len(issues) == 0) or (len(planned) > 0 and len(skipped) == 0),
        }

    def _collect_issues(self, world_id: str) -> List[TopologyIssue]:
        profile = self._get_profile(world_id)
        required_core_rooms = {
            str(x) for x in profile.get("required_core_rooms", []) if str(x).strip()
        }
        with db_session_context() as session:
            nodes = (
                session.query(Node)
                .filter(Node.attributes["world_id"].astext == str(world_id), Node.is_active == True)  # noqa: E712
                .all()
            )
            world_node_ids = (
                session.query(Node.id)
                .filter(Node.attributes["world_id"].astext == str(world_id), Node.is_active == True)  # noqa: E712
                .subquery()
            )
            rels = (
                session.query(Relationship)
                .filter(
                    Relationship.source_id.in_(world_node_ids),
                    Relationship.target_id.in_(world_node_ids),
                    Relationship.is_active == True,  # noqa: E712
                )
                .all()
            )

        issues: List[TopologyIssue] = []
        by_pkg_id: Dict[str, Node] = {}
        for n in nodes:
            pkg = str((n.attributes or {}).get("package_node_id") or "")
            if pkg:
                by_pkg_id[pkg] = n

        for need in required_core_rooms:
            if need not in by_pkg_id:
                issues.append(
                    TopologyIssue(
                        code="CORE_NODE_MISSING",
                        message=f"core room missing: {need}",
                        details={"required_node": need, "world_id": world_id},
                    )
                )

        pair_set: Set[Tuple[int, int]] = set()
        for r in rels:
            if r.type_code == "connects_to":
                pair_set.add((int(r.source_id), int(r.target_id)))
        for src, tgt in sorted(pair_set):
            if (tgt, src) not in pair_set:
                issues.append(
                    TopologyIssue(
                        code="CONNECTS_TO_REVERSE_MISSING",
                        message="reverse connects_to edge missing",
                        details={"source_id": src, "target_id": tgt, "world_id": world_id},
                    )
                )

        building_by_pkg: Dict[str, Node] = {}
        floors_per_building: Dict[str, int] = {}
        for n in nodes:
            tc = str(n.type_code or "")
            attrs = n.attributes or {}
            pkg = str(attrs.get("package_node_id") or "")
            if tc == "building" and pkg:
                building_by_pkg[pkg] = n
            if tc == "building_floor":
                bid = str(attrs.get("building_id") or "")
                if bid:
                    floors_per_building[bid] = floors_per_building.get(bid, 0) + 1
        for b_pkg, b_node in building_by_pkg.items():
            attrs = b_node.attributes or {}
            expected = attrs.get("floors_total")
            try:
                exp = int(expected)
            except (TypeError, ValueError):
                continue
            actual = int(floors_per_building.get(b_pkg, 0))
            if actual != exp:
                issues.append(
                    TopologyIssue(
                        code="FLOOR_COUNT_MISMATCH",
                        message=f"building floor count mismatch: {b_pkg}",
                        details={
                            "building_id": b_pkg,
                            "expected_floors_total": exp,
                            "actual_floor_nodes": actual,
                            "world_id": world_id,
                        },
                    )
                )
        return issues

    def _build_repair_actions(self, issues: List[TopologyIssue]) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []
        for issue in issues:
            if issue.code == "CONNECTS_TO_REVERSE_MISSING":
                actions.append(
                    {
                        "action": "create_reverse_connects_to",
                        "source_id": issue.details.get("source_id"),
                        "target_id": issue.details.get("target_id"),
                    }
                )
        return actions

    def _apply_create_reverse_connects_to(self, action: Dict[str, Any]) -> Dict[str, Any]:
        src = int(action["source_id"])
        tgt = int(action["target_id"])
        with db_session_context() as session:
            rt = session.query(RelationshipType).filter(RelationshipType.type_code == "connects_to").first()
            if not rt:
                return {"applied": False, "reason": "relationship_type_missing"}
            exists = (
                session.query(Relationship)
                .filter(
                    Relationship.source_id == tgt,
                    Relationship.target_id == src,
                    Relationship.type_code == "connects_to",
                    Relationship.is_active == True,  # noqa: E712
                )
                .first()
            )
            if exists:
                return {"applied": False, "reason": "already_exists"}
            rel = Relationship(
                uuid=uuidlib.uuid4(),
                type_id=rt.id,
                type_code="connects_to",
                source_id=tgt,
                target_id=src,
                is_active=True,
                attributes={},
                tags=[],
            )
            session.add(rel)
            session.commit()
        return {"applied": True}


world_topology_service = WorldTopologyService()

