"""Graph queries for semantic map drill-down layers."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.commands.room_connects_to_query import connects_to_exits_from_room
from app.models.graph import Node, Relationship

_FLOOR_MAP_VERTICAL_DIRECTIONS = frozenset({"up", "down"})


def _attrs(node: Node) -> Dict[str, Any]:
    return dict(node.attributes or {})


def _room_tags(node: Node) -> set[str]:
    return {str(tag).lower() for tag in (node.tags or [])}


def is_circulation_hub_room(room: Node) -> bool:
    """Circulation / elevator lobby room (indoor or outdoor)."""
    tags = _room_tags(room)
    attrs = _attrs(room)
    return "space:circulation" in tags or str(attrs.get("room_type") or "").strip().lower() == "circulation"


def is_campus_connector_room(room: Node) -> bool:
    """Outdoor spine or layer connector — never a building floor circulation hub."""
    if is_outdoor_landmark_room(room):
        return True
    return "layer:connector" in _room_tags(room)


def is_indoor_circulation_hub_room(room: Node) -> bool:
    """Indoor building circulation core for floor/campus hub resolution."""
    if is_campus_connector_room(room):
        return False
    return is_circulation_hub_room(room)


def has_campus_grid_position(room: Node) -> bool:
    """Room positioned on the campus-layer grid (outdoor spine / landmarks)."""
    attrs = _attrs(room)
    return attrs.get("campus_grid_col") is not None and attrs.get("campus_grid_row") is not None


def is_outdoor_landmark_room(room: Node) -> bool:
    """Outdoor or campus-spine landmark room (not building-indoor tile semantics)."""
    tags = _room_tags(room)
    if "environment:outdoor" in tags:
        return True
    return has_campus_grid_position(room) and "space:core" in tags


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
    if world is None:
        wid = str(_attrs(room).get("world_id") or "").strip().lower()
        if not wid and floor is not None:
            wid = str(_attrs(floor).get("world_id") or "").strip().lower()
        if not wid and building is not None:
            wid = str(_attrs(building).get("world_id") or "").strip().lower()
        if wid:
            world = (
                session.query(Node)
                .filter(
                    Node.type_code == "world",
                    Node.is_active == True,
                    Node.attributes["world_id"].astext == wid,
                )
                .first()
            )
    return floor, building, world


def building_for_floor(session: Session, floor: Node) -> Optional[Node]:
    """Resolve parent building for a floor anchor (graph location or package attr)."""
    if floor.location_id:
        parent = get_active_node(session, int(floor.location_id))
        if parent and str(parent.type_code) == "building":
            return parent
    bpkg = str(_attrs(floor).get("building_id") or "").strip()
    wid = str(_attrs(floor).get("world_id") or "").strip()
    if bpkg:
        hits = _nodes_by_attr(
            session,
            type_code="building",
            attr_key="package_node_id",
            attr_value=bpkg,
            world_id=wid,
        )
        if hits:
            return hits[0]
    return None


def world_for_building(session: Session, building: Node) -> Optional[Node]:
    """Resolve world node for a building anchor."""
    if building.location_id:
        parent = get_active_node(session, int(building.location_id))
        if parent and str(parent.type_code) == "world":
            return parent
    wid = str(_attrs(building).get("world_id") or "").strip().lower()
    if not wid:
        return None
    return (
        session.query(Node)
        .filter(
            Node.type_code == "world",
            Node.is_active == True,
            Node.attributes["world_id"].astext == wid,
        )
        .first()
    )


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


def _default_floor_map_anchor(floor_rooms: List[Node]) -> Optional[Node]:
    indoor_rooms = [room for room in floor_rooms if not is_campus_connector_room(room)]
    for room in indoor_rooms:
        if is_indoor_circulation_hub_room(room):
            return room
    return indoor_rooms[0] if indoor_rooms else None


def resolve_floor_map_anchor(floor_rooms: List[Node], location: Node) -> Optional[Node]:
    """Player room when on this floor; otherwise the floor circulation hub."""
    by_id = {int(room.id): room for room in floor_rooms}
    location_id = int(location.id)
    if location_id in by_id:
        return by_id[location_id]
    return _default_floor_map_anchor(floor_rooms)


def floor_map_look_exits(session: Session, anchor: Node) -> List[Dict[str, Any]]:
    """
    One-hop outgoing ``connects_to`` exits for floor map (``look`` SSOT).

    Omits vertical links only; floor stack handles ``up`` / ``down``.
    """
    rows: List[Dict[str, Any]] = []
    anchor_id = int(anchor.id)
    for row in connects_to_exits_from_room(session, anchor_id):
        direction = str(row.get("direction") or "").strip().lower()
        if direction in _FLOOR_MAP_VERTICAL_DIRECTIONS:
            continue
        rows.append(row)
    return rows


def rooms_for_floor_map(session: Session, floor: Node, anchor: Node) -> List[Node]:
    """
    Same-floor grid rooms for a floor plan — anchor plus one-hop ``look`` neighbors on this floor.
    """
    floor_rooms = rooms_on_floor(session, floor)
    by_id = {int(room.id): room for room in floor_rooms}
    floor_room_ids = set(by_id.keys())
    if not floor_room_ids:
        return []

    map_anchor = resolve_floor_map_anchor(floor_rooms, anchor)
    if not map_anchor:
        return floor_rooms
    anchor_id = int(map_anchor.id)

    visible: set[int] = {anchor_id}
    for row in floor_map_look_exits(session, map_anchor):
        neighbor_id = int(row["target_id"])
        if neighbor_id in floor_room_ids:
            visible.add(neighbor_id)

    return [by_id[room_id] for room_id in sorted(visible)]


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
    """Campus-layer spine rooms — ``campus_grid_*`` + ``space:core``, or outdoor-tagged."""
    rows = (
        session.query(Node)
        .filter(
            Node.type_code == "room",
            Node.is_active == True,
            Node.attributes["world_id"].astext == str(world_id),
        )
        .order_by(Node.id)
        .all()
    )
    landmarks = [room for room in rows if is_outdoor_landmark_room(room)]
    return sorted(
        landmarks,
        key=lambda n: (
            int(_attrs(n).get("campus_grid_row") or 0),
            int(_attrs(n).get("campus_grid_col") or 0),
            int(n.id),
        ),
    )


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


def _room_building_id(
    session: Session,
    room: Node,
    *,
    connector_ids: Optional[set[int]] = None,
) -> Optional[str]:
    if connector_ids and int(room.id) in connector_ids:
        return None
    floor, building, _ = resolve_ancestors(session, room)
    if not building:
        return None
    return str(_attrs(building).get("package_node_id") or building.id)


def _circulation_hub_rooms_by_building(
    session: Session,
    *,
    world_id: str,
    building_nodes: List[Node],
) -> Tuple[set[int], Dict[int, str]]:
    """First-floor circulation hub per building — tag/floor based, not package id patterns."""
    hub_ids: set[int] = set()
    room_to_building: Dict[int, str] = {}
    for building in building_nodes:
        bpkg = str(_attrs(building).get("package_node_id") or building.id)
        floors = floors_in_building(session, building)
        if not floors:
            continue
        first_floor = floors[0]
        floor_rooms = rooms_on_floor(session, first_floor)
        hub = _default_floor_map_anchor(floor_rooms)
        if hub is None:
            continue
        rid = int(hub.id)
        hub_ids.add(rid)
        room_to_building[rid] = bpkg
    return hub_ids, room_to_building


def campus_inter_building_edges(
    session: Session,
    world_id: str,
    *,
    building_nodes: List[Node],
    connector_nodes: List[Node],
) -> List[Relationship]:
    """connects_to edges that link buildings via connector rooms (campus layer)."""
    connector_ids = {int(node.id) for node in connector_nodes}
    hub_ids, room_to_building = _circulation_hub_rooms_by_building(
        session,
        world_id=world_id,
        building_nodes=building_nodes,
    )
    campus_room_ids: set[int] = set(connector_ids) | hub_ids
    if len(campus_room_ids) < 2:
        return []
    rels = (
        session.query(Relationship)
        .filter(
            Relationship.type_code == "connects_to",
            Relationship.is_active == True,
            Relationship.source_id.in_(campus_room_ids),
        )
        .all()
    )
    endpoint_ids: set[int] = set()
    for rel in rels:
        if rel.target_id not in campus_room_ids:
            continue
        endpoint_ids.add(int(rel.source_id))
        endpoint_ids.add(int(rel.target_id))
    if not endpoint_ids:
        return []
    nodes = (
        session.query(Node)
        .filter(Node.id.in_(endpoint_ids), Node.is_active == True)
        .all()
    )
    node_by_id = {int(node.id): node for node in nodes}

    def _building_pkg_for_room(room: Node) -> Optional[str]:
        rid = int(room.id)
        if rid in connector_ids:
            return None
        if rid in room_to_building:
            return room_to_building[rid]
        return _room_building_id(session, room, connector_ids=connector_ids)

    out: List[Relationship] = []
    for rel in rels:
        if rel.target_id not in campus_room_ids:
            continue
        src = node_by_id.get(int(rel.source_id))
        tgt = node_by_id.get(int(rel.target_id))
        if not src or not tgt:
            continue
        src_b = _building_pkg_for_room(src)
        tgt_b = _building_pkg_for_room(tgt)
        if src_b and tgt_b and src_b != tgt_b:
            out.append(rel)
            continue
        if int(src.id) in connector_ids or int(tgt.id) in connector_ids:
            if src_b != tgt_b:
                out.append(rel)
    return out


def hub_root_node(session: Session) -> Optional[Node]:
    from app.models.root_manager import root_manager

    if not root_manager.ensure_root_node_exists():
        return None
    return root_manager.get_root_node(session)


def world_map_entries(session: Session) -> Tuple[Optional[Node], List[Node], List[Node]]:
    """Return (hub_root, world_metadata_nodes, world_entrance_nodes)."""
    root = hub_root_node(session)
    world_nodes = list(
        session.query(Node)
        .filter(Node.type_code == "world", Node.is_active == True)
        .order_by(Node.id)
        .limit(50)
        .all()
    )
    entrances = list(
        session.query(Node)
        .filter(Node.type_code == "world_entrance", Node.is_active == True)
        .order_by(Node.id)
        .limit(50)
        .all()
    )
    return root, world_nodes, entrances


def room_contents(session: Session, room_id: int) -> Tuple[List[Node], List[Node], List[Node]]:
    """Return (occupants, devices, items) for a room logical map."""
    from app.commands.space_command import _rows_devices, _rows_occupants
    from app.models.graph import NodeType

    occupants = list(_rows_occupants(session, int(room_id)))
    devices = list(_rows_devices(session, int(room_id)))
    rels = (
        session.query(Relationship)
        .filter(
            Relationship.type_code == "located_in",
            Relationship.target_id == int(room_id),
            Relationship.is_active == True,
        )
        .all()
    )
    rel_source_ids = [int(rel.source_id) for rel in rels if rel.source_id]
    items_by_rel = (
        list(session.query(Node).filter(Node.id.in_(rel_source_ids), Node.is_active == True).all())
        if rel_source_ids
        else []
    )
    items_by_loc = (
        session.query(Node)
        .join(NodeType, Node.type_id == NodeType.id)
        .filter(
            Node.location_id == int(room_id),
            Node.is_active == True,
            NodeType.trait_class == "ITEM",
        )
        .order_by(Node.id)
        .all()
    )
    seen = {int(node.id) for node in items_by_rel}
    items: List[Node] = list(items_by_rel)
    for node in items_by_loc:
        if int(node.id) not in seen:
            items.append(node)
            seen.add(int(node.id))
    return occupants, devices, items


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
    if layer == "world":
        return hub_root_node(session) or location
    if layer == "floor":
        return floor
    if layer == "building":
        return building
    if layer == "campus":
        return world
    return location
