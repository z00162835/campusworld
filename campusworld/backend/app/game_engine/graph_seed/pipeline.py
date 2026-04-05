"""
Graph seed pipeline: PackageSnapshotV2 -> nodes + relationships (idempotent).
"""

from __future__ import annotations

import time
import uuid as uuidlib
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Set, Tuple, Union

from sqlalchemy.orm import Session

from app.game_engine.graph_seed.errors import GraphSeedError
from app.game_engine.graph_seed.ids import node_uuid
from app.game_engine.graph_seed.profile import WorldGraphProfile
from app.game_engine.runtime_store import WorldErrorCode
from app.models.graph import Node, NodeType, Relationship, RelationshipType

# node_types.type_code: entities that may be placed inside a room (Evennia: obj.location = room).
_LOCATABLE_IN_ROOM_TYPES = frozenset(
    {
        "npc_agent",
        "access_terminal",
        "world_object",
        "furniture",
        "network_access_point",
        "av_display",
        "lighting_fixture",
        "conference_seating",
        "lounge_furniture",
    }
)


def _sync_location_from_located_in(session: Session, source: Node, target: Node) -> None:
    """
    Scheme A: treat package ``located_in`` as the authority for room membership.
    Set SQL ``nodes.location_id`` so commands that query contents by location_id (e.g. look) work.
    """
    if str(target.type_code or "") != "room":
        return
    if str(source.type_code or "") not in _LOCATABLE_IN_ROOM_TYPES:
        return
    if source.location_id != target.id:
        source.location_id = target.id
        session.flush()


@dataclass
class _NodeSpec:
    logical_id: str
    package_type_code: str
    name: str
    attributes: Dict[str, Any]
    tags: List[Any]


def _snapshot_as_dict(snapshot: Any) -> Dict[str, Any]:
    if hasattr(snapshot, "world") and hasattr(snapshot, "spatial"):
        return {
            "world": snapshot.world,
            "spatial": snapshot.spatial,
            "entities": snapshot.entities,
            "relationships": snapshot.relationships,
            "meta": getattr(snapshot, "meta", {}) or {},
        }
    if isinstance(snapshot, dict):
        return snapshot
    raise GraphSeedError(WorldErrorCode.WORLD_DATA_INVALID.value, "snapshot must be PackageSnapshotV2 or dict")


def _build_specs(world_id: str, snap: Mapping[str, Any], profile: WorldGraphProfile) -> List[_NodeSpec]:
    specs: List[_NodeSpec] = []
    world = snap.get("world") or {}
    wid = str(world.get("id") or "")
    if not wid:
        raise GraphSeedError(
            WorldErrorCode.GRAPH_SEED_REFERENCE_BROKEN.value, "snapshot.world.id is required"
        )
    specs.append(
        _NodeSpec(
            logical_id=wid,
            package_type_code=str(world.get("type_code") or "world"),
            name=str(world.get("display_name") or wid)[:255],
            attributes={k: v for k, v in world.items() if k not in ("id", "type_code", "display_name", "tags")},
            tags=list(world.get("tags") or []),
        )
    )

    spatial = snap.get("spatial") or {}
    for b in spatial.get("buildings") or []:
        if not isinstance(b, dict) or not b.get("id"):
            continue
        bid = str(b["id"])
        specs.append(
            _NodeSpec(
                logical_id=bid,
                package_type_code=str(b.get("type_code") or "building"),
                name=str(b.get("display_name") or bid)[:255],
                attributes={k: v for k, v in b.items() if k not in ("id", "type_code", "display_name", "tags")},
                tags=list(b.get("tags") or []),
            )
        )
    for f in spatial.get("floors") or []:
        if not isinstance(f, dict) or not f.get("id"):
            continue
        fid = str(f["id"])
        specs.append(
            _NodeSpec(
                logical_id=fid,
                package_type_code=str(f.get("type_code") or "building_floor"),
                name=fid[:255],
                attributes={k: v for k, v in f.items() if k not in ("id", "type_code", "display_name", "tags")},
                tags=list(f.get("tags") or []),
            )
        )
    for r in spatial.get("rooms") or []:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        rid = str(r["id"])
        specs.append(
            _NodeSpec(
                logical_id=rid,
                package_type_code=str(r.get("type_code") or "room"),
                name=str(r.get("display_name") or rid)[:255],
                attributes={k: v for k, v in r.items() if k not in ("id", "type_code", "display_name", "tags")},
                tags=list(r.get("tags") or []),
            )
        )

    entities = snap.get("entities") or {}
    for bucket in ("zones", "npcs", "items"):
        for row in entities.get(bucket) or []:
            if not isinstance(row, dict) or not row.get("id"):
                continue
            eid = str(row["id"])
            specs.append(
                _NodeSpec(
                    logical_id=eid,
                    package_type_code=str(row.get("type_code") or ""),
                    name=str(row.get("display_name") or eid)[:255],
                    attributes=_entity_row_flat_attributes(row),
                    tags=list(row.get("tags") or []),
                )
            )
    return specs


def _entity_row_flat_attributes(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge package row top-level fields with nested ``attributes`` dict.

    YAML entities keep device/item fields under ``attributes:``; without merging,
    keys like ``room_list_name`` stay nested and look/typeclasses never see them.
    """
    skip = frozenset({"id", "type_code", "display_name", "tags", "world_id"})
    top: Dict[str, Any] = {}
    for k, v in row.items():
        if k in skip or k == "attributes":
            continue
        top[k] = v
    nested = row.get("attributes")
    if isinstance(nested, dict):
        return {**top, **nested}
    return top


def _load_node_type_map(session: Session) -> Dict[str, NodeType]:
    rows = session.query(NodeType).all()
    return {r.type_code: r for r in rows}


def _load_rel_type_map(session: Session) -> Dict[str, RelationshipType]:
    rows = session.query(RelationshipType).all()
    return {r.type_code: r for r in rows}


def _upsert_node(
    session: Session,
    world_id: str,
    spec: _NodeSpec,
    profile: WorldGraphProfile,
    nt_map: Dict[str, NodeType],
) -> Tuple[Node, str]:
    db_type = profile.map_node_type(spec.package_type_code)

    nt = nt_map.get(db_type)
    if not nt:
        raise GraphSeedError(
            WorldErrorCode.GRAPH_SEED_TYPE_UNKNOWN.value,
            f"node_types row missing for type_code={db_type}",
        )

    nuuid = node_uuid(world_id, spec.logical_id)
    existing = session.query(Node).filter(Node.uuid == nuuid).first()
    merged_attrs = dict(spec.attributes)
    merged_attrs["world_id"] = world_id
    merged_attrs["package_node_id"] = spec.logical_id

    if existing:
        existing.name = spec.name
        existing.attributes = {**(existing.attributes or {}), **merged_attrs}
        existing.tags = spec.tags
        existing.type_id = nt.id
        existing.type_code = db_type
        return existing, "skipped"

    node = Node(
        uuid=nuuid,
        type_id=nt.id,
        type_code=db_type,
        name=spec.name,
        description=None,
        is_active=True,
        is_public=True,
        access_level="normal",
        attributes=merged_attrs,
        tags=spec.tags,
    )
    session.add(node)
    session.flush()
    return node, "created"


def _ensure_relationship(
    session: Session,
    rt_map: Dict[str, RelationshipType],
    source: Node,
    target: Node,
    type_code: str,
    attributes: Optional[Dict[str, Any]] = None,
) -> str:
    rt = rt_map.get(type_code)
    if not rt:
        raise GraphSeedError(
            WorldErrorCode.GRAPH_SEED_TYPE_UNKNOWN.value,
            f"relationship_types row missing for type_code={type_code}",
        )
    exists = (
        session.query(Relationship)
        .filter(
            Relationship.source_id == source.id,
            Relationship.target_id == target.id,
            Relationship.type_code == type_code,
            Relationship.is_active.is_(True),
        )
        .first()
    )
    if exists:
        return "skipped"
    rel = Relationship(
        uuid=uuidlib.uuid4(),
        type_id=rt.id,
        type_code=type_code,
        source_id=source.id,
        target_id=target.id,
        is_active=True,
        attributes=attributes or {},
        tags=[],
    )
    session.add(rel)
    session.flush()
    return "created"


def _effective_strict_relationships(
    profile: WorldGraphProfile, strict_relationships: Optional[bool]
) -> bool:
    if strict_relationships is not None:
        return strict_relationships
    return bool(getattr(profile, "strict_relationships", False))


def run_graph_seed(
    session: Session,
    world_id: str,
    snapshot: Any,
    profile: WorldGraphProfile,
    *,
    strict_relationships: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Execute idempotent seed inside an open SQLAlchemy session (caller commits).

    If strict_relationships is True (or profile.strict_relationships), any snapshot
    relationship whose rel_type_code is not in profile.allowed_relationship_type_codes
    raises GraphSeedError(GRAPH_SEED_RELATIONSHIP_UNSUPPORTED). Otherwise those rows are
    skipped and counted in details.relationships_ignored_*.
    """
    t0 = time.perf_counter()
    snap = _snapshot_as_dict(snapshot)
    if str(world_id) != str(profile.world_package_id):
        raise GraphSeedError(
            WorldErrorCode.GRAPH_SEED_REFERENCE_BROKEN.value,
            f"world_id {world_id!r} does not match profile.world_package_id {profile.world_package_id!r}",
        )

    nt_map = _load_node_type_map(session)
    rt_map = _load_rel_type_map(session)
    allowed_rels = profile.allowed_relationship_type_codes

    specs = _build_specs(world_id, snap, profile)
    id_to_node: Dict[str, Node] = {}
    nodes_created = 0
    nodes_skipped = 0

    for spec in specs:
        node, status = _upsert_node(session, world_id, spec, profile, nt_map)
        id_to_node[spec.logical_id] = node
        if status == "created":
            nodes_created += 1
        else:
            nodes_skipped += 1

    rels: List[Dict[str, Any]] = list(snap.get("relationships") or [])
    connects_pairs: Set[Tuple[str, str]] = set()
    rels_created = 0
    rels_skipped = 0
    strict = _effective_strict_relationships(profile, strict_relationships)
    ign_by_type: Dict[str, int] = {}
    ign_sample: List[Dict[str, str]] = []
    _IGN_SAMPLE_MAX = 10

    for rel in rels:
        if not isinstance(rel, dict):
            continue
        rtc = str(rel.get("rel_type_code") or "")
        if not rtc:
            continue
        if rtc not in allowed_rels:
            if strict:
                raise GraphSeedError(
                    WorldErrorCode.GRAPH_SEED_RELATIONSHIP_UNSUPPORTED.value,
                    f"relationship type not allowed by graph profile (strict): "
                    f"id={rel.get('id')!r} rel_type_code={rtc!r}",
                )
            ign_by_type[rtc] = ign_by_type.get(rtc, 0) + 1
            if len(ign_sample) < _IGN_SAMPLE_MAX:
                ign_sample.append(
                    {
                        "id": str(rel.get("id") or ""),
                        "rel_type_code": rtc,
                    }
                )
            continue
        src_id = str(rel.get("source_id") or "")
        tgt_id = str(rel.get("target_id") or "")
        src_n = id_to_node.get(src_id)
        tgt_n = id_to_node.get(tgt_id)
        if not src_n or not tgt_n:
            raise GraphSeedError(
                WorldErrorCode.GRAPH_SEED_REFERENCE_BROKEN.value,
                f"relationship endpoints not loaded: {rel.get('id')} {src_id}->{tgt_id}",
            )
        sw = str((src_n.attributes or {}).get("world_id") or "")
        tw = str((tgt_n.attributes or {}).get("world_id") or "")
        if sw and tw and sw != tw:
            raise GraphSeedError(
                WorldErrorCode.GRAPH_SEED_REFERENCE_BROKEN.value,
                f"relationship crosses world boundary in snapshot (disallowed; use admin bridge): "
                f"id={rel.get('id')!r} {sw!r}->{tw!r}",
            )
        if rtc == "connects_to":
            connects_pairs.add((src_id, tgt_id))
        st = _ensure_relationship(
            session,
            rt_map,
            src_n,
            tgt_n,
            rtc,
            dict(rel.get("attributes") or {}),
        )
        if rtc == "located_in":
            _sync_location_from_located_in(session, src_n, tgt_n)
        if st == "created":
            rels_created += 1
        else:
            rels_skipped += 1

    # Bidirectional connects_to: add reverse when only one directed edge declared
    for a, b in list(connects_pairs):
        if (b, a) not in connects_pairs:
            na = id_to_node.get(a)
            nb = id_to_node.get(b)
            if na and nb:
                st = _ensure_relationship(session, rt_map, nb, na, "connects_to", {})
                if st == "created":
                    rels_created += 1
                else:
                    rels_skipped += 1

    duration_ms = int((time.perf_counter() - t0) * 1000)
    ign_total = sum(ign_by_type.values())
    return {
        "ok": True,
        "error_code": None,
        "message": "graph seed completed",
        "details": {
            "nodes_upserted": nodes_created,
            "nodes_skipped": nodes_skipped,
            "relationships_created": rels_created,
            "relationships_skipped": rels_skipped,
            "relationships_ignored_count": ign_total,
            "relationships_ignored_by_type": dict(sorted(ign_by_type.items())),
            "relationships_ignored_sample": ign_sample,
            "strict_relationships": strict,
            "duration_ms": duration_ms,
        },
    }
