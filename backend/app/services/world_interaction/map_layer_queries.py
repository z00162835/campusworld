"""Graph queries for semantic map drill-down layers."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.graph import Node, Relationship

OUTDOOR_LANDMARK_PACKAGE_IDS = frozenset(
    {"hicampus_gate", "hicampus_bridge", "hicampus_plaza"},
)


def _attrs(node: Node) -> Dict[str, Any]:
    return dict(node.attributes or {})


def get_active_node(session: Session, node_id: int) -> Optional[Node]:
    return (
        session.query(Node)
        .filter(Node.id == int(node_id), Node.is_active == True)
        .first()
    )


def resolve_ancestors(session: Session, room: Node) -> Tuple[Optional[Node], Optional[Node], Optional[Node]]:
    """Return (floor, building, world) for a room node."""
    floor = building = world = None
    if room.location_id:
        floor = get_active_node(session, int(room.location_id))
    if floor and floor.location_id:
        building = get_active_node(session, int(floor.location_id))
    if building and building.location_id:
        world = get_active_node(session, int(building.location_id))
    return floor, building, world


def _nodes_by_location(session: Session, parent_id: int, type_code: str) -> List[Node]:
    return (
        session.query(Node)
        .filter(
            Node.location_id == int(parent_id),
            Node.type_code == type_code,
            Node.is_active == True,
        )
        .order_by(Node.id)
        .all()
    )


def _nodes_by_attr(
    session: Session,
    *,
    type_code: str,
    attr_key: str,
    attr_value: str,
    world_id: str = "",
) -> List[Node]:
    q = session.query(Node).filter(
        Node.type_code == type_code,
        Node.is_active == True,
        Node.attributes[attr_key].astext == str(attr_value),
    )
    if world_id:
        q = q.filter(Node.attributes["world_id"].astext == str(world_id))
    return list(q.order_by(Node.id).all())


def rooms_on_floor(session: Session, floor: Node) -> List[Node]:
    rows = _nodes_by_location(session, int(floor.id), "room")
    if rows:
        return rows
    fpkg = str(_attrs(floor).get("package_node_id") or "").strip()
    wid = str(_attrs(floor).get("world_id") or "").strip()
    if fpkg:
        return _nodes_by_attr(session, type_code="room", attr_key="floor_id", attr_value=fpkg, world_id=wid)
    return []


def floors_in_building(session: Session, building: Node) -> List[Node]:
    rows = _nodes_by_location(session, int(building.id), "building_floor")
    if rows:
        return sorted(rows, key=_floor_sort_key)
    bpkg = str(_attrs(building).get("package_node_id") or "").strip()
    wid = str(_attrs(building).get("world_id") or "").strip()
    if bpkg:
        hit = _nodes_by_attr(
            session,
            type_code="building_floor",
            attr_key="building_id",
            attr_value=bpkg,
            world_id=wid,
        )
        return sorted(hit, key=_floor_sort_key)
    return []


def _floor_sort_key(floor: Node) -> Tuple[int, str]:
    attrs = _attrs(floor)
    try:
        num = int(attrs.get("floor_number") or attrs.get("floor_no") or 0)
    except (TypeError, ValueError):
        num = 0
    return (num, str(floor.id))


def buildings_in_world(session: Session, world_id: str) -> List[Node]:
    q = session.query(Node).filter(
        Node.type_code == "building",
        Node.is_active == True,
        Node.attributes["world_id"].astext == str(world_id),
    )
    rows = list(q.order_by(Node.id).all())
    return sorted(rows, key=lambda n: str(_attrs(n).get("building_code") or n.name or ""))


def outdoor_landmark_rooms(session: Session, world_id: str) -> List[Node]:
    q = session.query(Node).filter(
        Node.type_code == "room",
        Node.is_active == True,
        Node.attributes["world_id"].astext == str(world_id),
    )
    out: List[Node] = []
    for node in q.all():
        pkg = str(_attrs(node).get("package_node_id") or "").strip()
        tags = [str(t).lower() for t in (node.tags or [])]
        if pkg in OUTDOOR_LANDMARK_PACKAGE_IDS or "environment:outdoor" in tags:
            out.append(node)
    return sorted(out, key=lambda n: str(_attrs(n).get("package_node_id") or n.id))


def outdoor_landmark_edges(session: Session, world_id: str) -> List[Relationship]:
    """Return connects_to edges whose endpoints are outdoor landmark rooms."""
    outdoors = outdoor_landmark_rooms(session, world_id)
    if len(outdoors) < 2:
        return []
    id_set = {int(node.id) for node in outdoors}
    rels = (
        session.query(Relationship)
        .filter(
            Relationship.type_code == "connects_to",
            Relationship.is_active == True,
            Relationship.source_id.in_(id_set),
        )
        .all()
    )
    return [rel for rel in rels if rel.target_id in id_set]


def resolve_anchor_node(
    session: Session,
    *,
    view_layer: str,
    anchor_id: Optional[str],
    location: Node,
) -> Optional[Node]:
    if anchor_id and str(anchor_id).isdigit():
        node = get_active_node(session, int(anchor_id))
        if node:
            return node
    floor, building, world = resolve_ancestors(session, location)
    layer = str(view_layer or "room").strip().lower()
    if layer == "floor":
        return floor
    if layer == "building":
        return building
    if layer == "campus":
        return world
    return location
