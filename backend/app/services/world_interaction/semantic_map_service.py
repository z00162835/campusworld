"""Semantic map focus graph builder for world interaction UI."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.commands.room_connects_to_query import connects_to_exits_from_room
from app.game_engine.direction_util import normalize_direction
from app.models.graph import Node, Relationship

from .map_geometry import (
    MAP_GRID_CELL_PX,
    MAP_GRID_ORIGIN_X,
    MAP_GRID_ORIGIN_Y,
    grid_to_map_coords,
    room_has_map_grid,
)
from .map_layer_queries import (
    building_for_floor,
    buildings_in_world,
    campus_inter_building_edges,
    floor_map_look_exits,
    floors_in_building,
    get_active_node,
    hub_root_node,
    is_outdoor_landmark_room,
    outdoor_landmark_edges,
    outdoor_landmark_rooms,
    resolve_floor_map_anchor,
    resolve_anchor_node,
    resolve_ancestors,
    room_contents,
    rooms_for_floor_map,
    rooms_on_floor,
    world_for_building,
    world_map_entries,
)
from .map_layout import (
    assign_neighbor_positions,
    campus_grid_position,
    floor_grid_compass_position,
    horizontal_row_positions,
    logical_zone_positions,
    vertical_stack_positions,
)
from .types import DISPLAY_POLICY

VIEW_LAYERS = frozenset({"room", "floor", "building", "campus", "world"})
MAP_MODES = frozenset({"focus", "route", "agent", "event"})
_VERTICAL_EDGE_DIRECTIONS = frozenset({"up", "down"})
logger = logging.getLogger(__name__)


def _display_name(node: Optional[Node]) -> str:
    if not node:
        return "Unknown"
    attrs = dict(node.attributes or {})
    type_code = str(node.type_code or "")
    if type_code == "building_floor":
        return str(
            attrs.get("display_name")
            or attrs.get("floor_name")
            or attrs.get("name")
            or node.name
        )
    if type_code == "building":
        return str(
            attrs.get("display_name")
            or attrs.get("building_name")
            or attrs.get("name")
            or node.name
        )
    return str(attrs.get("display_name") or attrs.get("room_name") or attrs.get("name") or node.name)


def _hub_display_name(hub: Optional[Node]) -> str:
    if not hub:
        return "Singularity Room"
    attrs = dict(hub.attributes or {})
    return str(attrs.get("room_name") or attrs.get("display_name") or hub.name or "Singularity Room")


def _same_building(session: Session, left: Node, right: Node) -> bool:
    if is_outdoor_landmark_room(left) or is_outdoor_landmark_room(right):
        if is_outdoor_landmark_room(left) and is_outdoor_landmark_room(right):
            return True
        return False
    _, left_building, _ = resolve_ancestors(session, left)
    _, right_building, _ = resolve_ancestors(session, right)
    if left_building and right_building:
        return int(left_building.id) == int(right_building.id)
    left_attrs = dict(left.attributes or {})
    right_attrs = dict(right.attributes or {})
    left_code = str(left_attrs.get("building_id") or "").strip()
    right_code = str(right_attrs.get("building_id") or "").strip()
    if left_code and right_code:
        return left_code == right_code
    return False


def _building_for_room(session: Session, room: Node) -> Optional[Node]:
    _, building, _ = resolve_ancestors(session, room)
    if building:
        return building
    floor, _, _ = resolve_ancestors(session, room)
    if floor:
        return building_for_floor(session, floor)
    return None


def _resolve_exit_display_node(
    session: Session,
    source: Node,
    target: Node,
    *,
    target_display_name: str = "",
) -> Tuple[Node, bool, str]:
    """Pick exit label node: cross-building indoor targets show building; else room/outdoor."""
    cross_building = not _same_building(session, source, target)
    if is_outdoor_landmark_room(target):
        label = target_display_name or _display_name(target)
        return target, cross_building, label
    if cross_building:
        target_building = _building_for_room(session, target)
        if target_building:
            return target_building, True, _display_name(target_building)
    label = target_display_name or _display_name(target)
    return target, cross_building, label


def _align_breadcrumb_context(
    session: Session,
    *,
    view_layer: str,
    room: Optional[Node] = None,
    floor: Optional[Node] = None,
    building: Optional[Node] = None,
    world: Optional[Node] = None,
) -> Tuple[Optional[Node], Optional[Node], Optional[Node], Optional[Node]]:
    """Prefer map-anchor ancestry over caller hints; log and correct mismatches."""
    layer = str(view_layer or "room").strip().lower()
    resolved_room = room
    resolved_floor = floor
    resolved_building = building
    resolved_world = world

    if room and layer == "room" and not is_outdoor_landmark_room(room):
        anchor_floor, anchor_building, anchor_world = resolve_ancestors(session, room)
        if building and anchor_building and int(building.id) != int(anchor_building.id):
            logger.warning(
                "Breadcrumb building mismatch for room %s: hint=%s anchor=%s",
                room.id,
                building.id,
                anchor_building.id,
            )
        if floor and anchor_floor and int(floor.id) != int(anchor_floor.id):
            logger.warning(
                "Breadcrumb floor mismatch for room %s: hint=%s anchor=%s",
                room.id,
                floor.id,
                anchor_floor.id,
            )
        resolved_floor, resolved_building, resolved_world = anchor_floor, anchor_building, anchor_world or world

    elif floor and layer == "floor":
        anchor_building = building_for_floor(session, floor)
        anchor_world = world_for_building(session, anchor_building) if anchor_building else None
        if building and anchor_building and int(building.id) != int(anchor_building.id):
            logger.warning(
                "Breadcrumb building mismatch for floor %s: hint=%s anchor=%s",
                floor.id,
                building.id,
                anchor_building.id,
            )
        resolved_building = anchor_building or building
        resolved_world = anchor_world or world

    elif building and layer == "building":
        anchor_world = world_for_building(session, building)
        if world and anchor_world and int(world.id) != int(anchor_world.id):
            logger.warning(
                "Breadcrumb world mismatch for building %s: hint=%s anchor=%s",
                building.id,
                world.id,
                anchor_world.id,
            )
        resolved_world = anchor_world or world

    return resolved_room, resolved_floor, resolved_building, resolved_world


def _map_node_type(node: Node) -> str:
    type_code = str(node.type_code or "")
    attrs = dict(node.attributes or {})
    tags = [str(t).lower() for t in (node.tags or [])]
    if attrs.get("is_root") is True or str(attrs.get("is_root")).lower() == "true":
        return "hub"
    if type_code == "world":
        return "world"
    if type_code == "world_entrance":
        return "gate"
    if type_code == "building_floor":
        return "floor"
    if "building" in type_code:
        return "building"
    if "room" in type_code:
        room_type = str(attrs.get("room_type") or "").strip().lower()
        if is_outdoor_landmark_room(node):
            if "layer:entry" in tags or room_type == "landmark":
                return "gate"
            if "layer:connector" in tags:
                return "bridge"
            if room_type == "plaza" or "plaza" in tags:
                return "plaza"
            return "outdoor"
        if "environment:outdoor" in tags or room_type == "circulation":
            return "outdoor"
        return "room"
    trait = str(getattr(node, "trait_class", "") or "").upper()
    if trait == "DEVICE":
        return "device"
    if trait == "ITEM":
        return "object"
    if trait == "AGENT" or type_code in {"npc_agent", "account"}:
        return "agent"
    return "service"


def _map_node_payload(
    node: Node,
    status: str,
    x: int,
    y: int,
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    attrs = dict(node.attributes or {})
    payload: Dict[str, Any] = {
        "id": str(node.id),
        "name": _display_name(node),
        "type": _map_node_type(node),
        "x": x,
        "y": y,
        "status": status,
        "semanticTags": list(node.tags or [])[:4],
        "activeAgentIds": [],
        "activeEventIds": [],
        "objectIds": [],
    }
    if attrs.get("building_id"):
        payload["buildingId"] = str(attrs.get("building_id"))
    if attrs.get("floor_id"):
        payload["floorId"] = str(attrs.get("floor_id"))
    floor_no = attrs.get("floor_number") or attrs.get("floor_no")
    if floor_no is not None:
        try:
            payload["floorNumber"] = int(floor_no)
        except (TypeError, ValueError):
            pass
    if extra:
        payload.update(extra)
    return payload


_ROOM_CONTENT_GROUP_LABEL: Dict[str, str] = {
    "occupant": "People",
    "device": "Devices",
    "item": "Items",
}


def _room_content_group_node(
    room_id: int,
    zone: str,
    members: List[Node],
    *,
    x: int,
    y: int,
    selected_entity_id: Optional[str],
) -> Dict[str, Any]:
    """Single grouped node for devices or items (one edge to room hub)."""
    member_ids = [str(int(member.id)) for member in members]
    prefix = _ROOM_CONTENT_GROUP_LABEL.get(zone, zone.title())
    count = len(members)
    name = f"{prefix} · {count}"
    group_members: List[Dict[str, Any]] = []
    for member in members:
        member_id = str(int(member.id))
        member_status = "active" if selected_entity_id and member_id == str(selected_entity_id) else "visible"
        group_members.append(
            {
                "id": member_id,
                "name": _display_name(member),
                "type": _map_node_type(member),
                "status": member_status,
            }
        )
    status = "visible"
    if selected_entity_id and str(selected_entity_id) in member_ids:
        status = "active"
    return {
        "id": f"cluster:room:{room_id}:{zone}",
        "name": name,
        "type": "cluster",
        "x": x,
        "y": y,
        "status": status,
        "semanticTags": [zone, "group"],
        "activeAgentIds": [],
        "activeEventIds": [],
        "objectIds": list(member_ids),
        "groupMembers": group_members,
        "logicalZone": zone,
        "overflowCount": 0,
    }


def _room_occupant_entries(
    occupants: List[Node],
    *,
    selected_entity_id: Optional[str],
) -> List[Dict[str, Any]]:
    """Sidebar list for people in the room (not drawn on the compass map)."""
    entries: List[Dict[str, Any]] = []
    for occupant in occupants:
        occupant_id = str(int(occupant.id))
        status = "active" if selected_entity_id and occupant_id == str(selected_entity_id) else "visible"
        entries.append(
            {
                "id": occupant_id,
                "name": _display_name(occupant),
                "type": _map_node_type(occupant),
                "status": status,
            }
        )
    return entries


def _append_room_content_groups(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    location: Node,
    *,
    devices: List[Node],
    items: List[Node],
    selected_entity_id: Optional[str],
) -> None:
    room_id = int(location.id)
    for zone, members in (
        ("device", devices),
        ("item", items),
    ):
        if not members:
            continue
        x, y = logical_zone_positions(1, zone)[0]
        nodes.append(
            _room_content_group_node(
                room_id,
                zone,
                members,
                x=x,
                y=y,
                selected_entity_id=selected_entity_id,
            )
        )


def _edge_direction(rel: Relationship, target: Node) -> str:
    attrs = dict(rel.attributes or {})
    raw = str(attrs.get("direction") or rel.target_role or "").strip().lower()
    if raw:
        return normalize_direction(raw)
    pkg = str((target.attributes or {}).get("package_node_id") or "").strip().lower()
    return pkg if pkg else ""


def _neighbor_links(session: Session, location: Node) -> List[Dict[str, Any]]:
    links: List[Dict[str, Any]] = []
    for row in connects_to_exits_from_room(session, int(location.id)):
        links.append(
            {
                "direction": str(row.get("direction") or ""),
                "targetId": str(row["target_id"]),
                "targetName": str(row.get("target_display_name") or ""),
                "summary": str(row.get("target_short_desc") or ""),
            }
        )
    return links


def _agents_near(session: Session, location_ids: List[int]) -> List[Dict[str, Any]]:
    if not location_ids:
        return []
    from datetime import datetime

    agents = (
        session.query(Node)
        .filter(
            Node.location_id.in_(location_ids),
            Node.type_code == "npc_agent",
            Node.is_active == True,
        )
        .limit(DISPLAY_POLICY["maxAgentsHighlighted"])
        .all()
    )
    out: List[Dict[str, Any]] = []
    now = datetime.utcnow().isoformat()
    for agent in agents:
        attrs = dict(agent.attributes or {})
        out.append(
            {
                "agentId": str(agent.id),
                "name": _display_name(agent),
                "role": str(attrs.get("role") or "guide"),
                "currentSpaceId": str(agent.location_id),
                "status": str(attrs.get("status") or "waiting"),
                "currentIntent": attrs.get("current_intent"),
                "currentTask": attrs.get("current_task"),
                "lastSeenAt": now,
                "visibility": "visible",
            }
        )
    return out


def _apply_mode_highlights(focus_map: Dict[str, Any], mode: str) -> Dict[str, Any]:
    """D12: filter highlights only; dataset unchanged."""
    clean_mode = mode if mode in MAP_MODES else "focus"
    focus_map = dict(focus_map)
    focus_map["mode"] = clean_mode
    nodes = list(focus_map.get("nodes") or [])
    edges = list(focus_map.get("edges") or [])
    agents = list(focus_map.get("agentPresences") or [])
    current_id = focus_map.get("currentSpaceId")

    if clean_mode == "agent":
        agent_space_ids = {str(a.get("currentSpaceId")) for a in agents}
        updated: List[Dict[str, Any]] = []
        for node in nodes:
            n = dict(node)
            if n.get("id") in agent_space_ids and n.get("status") != "current":
                n["status"] = "active"
            updated.append(n)
        focus_map["nodes"] = updated
        return focus_map

    if clean_mode == "route":
        path = focus_map.get("highlightedPath") or []
        path_ids = set(path)
        updated_nodes: List[Dict[str, Any]] = []
        for node in nodes:
            n = dict(node)
            if str(n.get("id")) in path_ids:
                n["status"] = "current" if str(n.get("id")) == str(current_id) else "active"
            updated_nodes.append(n)
        updated_edges: List[Dict[str, Any]] = []
        for edge in edges:
            e = dict(edge)
            if str(e.get("from")) in path_ids and str(e.get("to")) in path_ids:
                e["status"] = "recommended"
            updated_edges.append(e)
        focus_map["nodes"] = updated_nodes
        focus_map["edges"] = updated_edges
        return focus_map

    if clean_mode == "event":
        event_ids = {str(i) for i in (focus_map.get("eventSpaceIds") or []) if str(i)}
        max_hotspots = int(DISPLAY_POLICY.get("maxEventHotspotsHighlighted", 2))
        hotspot_ids = list(event_ids)[:max_hotspots]
        updated_event_nodes: List[Dict[str, Any]] = []
        for node in nodes:
            n = dict(node)
            nid = str(n.get("id"))
            if nid in hotspot_ids:
                n["status"] = "current" if nid == str(current_id) else "active"
                n["activeEventIds"] = list(n.get("activeEventIds") or []) + ["decision"]
            updated_event_nodes.append(n)
        focus_map["nodes"] = updated_event_nodes
        return focus_map

    return focus_map


def _breadcrumb_chain(
    session: Session,
    *,
    view_layer: str = "room",
    hub: Optional[Node] = None,
    world: Optional[Node] = None,
    building: Optional[Node] = None,
    floor: Optional[Node] = None,
    room: Optional[Node] = None,
    campus_spot: Optional[Node] = None,
) -> List[Dict[str, str]]:
    """Navigation breadcrumb for the active map layer (not player location ancestry)."""
    room, floor, building, world = _align_breadcrumb_context(
        session,
        view_layer=view_layer,
        room=room,
        floor=floor,
        building=building,
        world=world,
    )
    crumbs: List[Dict[str, str]] = []
    layer = str(view_layer or "room").strip().lower()

    if layer == "world" and hub:
        return [{"layer": "world", "id": str(hub.id), "name": _hub_display_name(hub), "role": "hub"}]

    if hub and layer in {"campus", "building", "floor", "room"}:
        crumbs.append({"layer": "world", "id": str(hub.id), "name": _hub_display_name(hub), "role": "hub"})
    if world and layer in {"campus", "building", "floor", "room"}:
        crumbs.append({"layer": "campus", "id": str(world.id), "name": _display_name(world), "role": "world"})
    if layer == "campus" and campus_spot:
        crumbs.append(
            {
                "layer": "campus",
                "id": str(campus_spot.id),
                "name": _display_name(campus_spot),
                "role": "campus_spot",
            }
        )
        return crumbs
    if building and layer in {"building", "room"}:
        crumbs.append({"layer": "building", "id": str(building.id), "name": _display_name(building), "role": "building"})
    if floor and layer in {"floor", "room"}:
        crumbs.append({"layer": "floor", "id": str(floor.id), "name": _display_name(floor), "role": "floor"})
    if room and layer == "room":
        crumbs.append({"layer": "room", "id": str(room.id), "name": _display_name(room), "role": "room"})
    return crumbs


def _node_status(node: Node, *, current_space_id: str, selected_entity_id: Optional[str]) -> str:
    nid = str(node.id)
    if nid == str(current_space_id):
        return "current"
    if selected_entity_id and nid == str(selected_entity_id):
        return "active"
    return "visible"


def _intra_floor_edges(session: Session, room_ids: List[int]) -> List[Relationship]:
    if not room_ids:
        return []
    id_set = set(room_ids)
    rels = (
        session.query(Relationship)
        .filter(
            Relationship.type_code == "connects_to",
            Relationship.is_active == True,
            Relationship.source_id.in_(room_ids),
        )
        .all()
    )
    return [r for r in rels if r.target_id in id_set]


def _cap_room_focus_graph(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    *,
    cap: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Keep hub + exits + content groups; drop only if still over cap (rare)."""
    essential = [
        n
        for n in nodes
        if n.get("logicalZone") in {"hub", "exit"}
        or (n.get("type") == "cluster" and str(n.get("id", "")).startswith("cluster:room:"))
    ]
    essential_ids = {str(n["id"]) for n in essential}
    optional = [n for n in nodes if str(n["id"]) not in essential_ids]
    remaining = max(0, int(cap) - len(essential))
    visible_nodes = essential + optional[:remaining]
    visible_ids = {str(n["id"]) for n in visible_nodes}
    visible_edges = [
        edge
        for edge in edges
        if str(edge.get("from") or "") in visible_ids and str(edge.get("to") or "") in visible_ids
    ]
    return visible_nodes, visible_edges


def build_room_focus_map(
    session: Session,
    location: Node,
    *,
    mode: str = "focus",
    selected_entity_id: Optional[str] = None,
    floor: Optional[Node] = None,
    building: Optional[Node] = None,
    world: Optional[Node] = None,
    hub: Optional[Node] = None,
) -> Dict[str, Any]:
    """Build logical room map: hub + occupants / items / devices / exits."""
    occupants, devices, items = room_contents(session, int(location.id))
    device_ids = {int(node.id) for node in devices}
    items = [node for node in items if int(node.id) not in device_ids]
    max_visible = int(DISPLAY_POLICY["maxMapNodesVisible"]) - 1
    exit_rows = connects_to_exits_from_room(session, int(location.id))[:max_visible]

    nodes: List[Dict[str, Any]] = [
        _map_node_payload(location, "current", 50, 50, extra={"logicalZone": "hub"}),
    ]
    edges: List[Dict[str, Any]] = []

    _append_room_content_groups(
        nodes,
        edges,
        location,
        devices=devices,
        items=items,
        selected_entity_id=selected_entity_id,
    )

    exit_entries: List[Tuple[str, str]] = []
    resolved_exits: List[Tuple[Dict[str, Any], Node, Node, bool, str]] = []
    for row in exit_rows:
        target_id = int(row["target_id"])
        target = get_active_node(session, target_id)
        if not target:
            continue
        display_node, cross_building, target_label = _resolve_exit_display_node(
            session,
            location,
            target,
            target_display_name=str(row.get("target_display_name") or ""),
        )
        resolved_exits.append((row, target, display_node, cross_building, target_label))
        exit_entries.append((str(row.get("direction") or ""), str(display_node.id)))
    exit_positions = assign_neighbor_positions(exit_entries)
    for index, (row, target, display_node, cross_building, target_label) in enumerate(resolved_exits):
        display_id = str(display_node.id)
        x, y = exit_positions[index] if index < len(exit_positions) else (50, 78)
        direction = str(row.get("direction") or "")
        status = _node_status(display_node, current_space_id=str(location.id), selected_entity_id=selected_entity_id)
        exit_extra: Dict[str, Any] = {"logicalZone": "exit", "direction": direction}
        if cross_building:
            exit_extra["crossBuilding"] = True
        if int(display_node.id) != int(target.id):
            exit_extra["drillAnchorId"] = str(target.id)
        nodes.append(
            _map_node_payload(
                display_node,
                status,
                x,
                y,
                extra=exit_extra,
            )
        )
        edge_status = "recommended" if index == 0 and not cross_building else "available"
        if cross_building:
            edge_status = "cross-building"
        edges.append(
            {
                "id": f"logical_exit_{location.id}_{target.id}",
                "from": str(location.id),
                "to": display_id,
                "label": direction,
                "direction": direction,
                "status": edge_status,
                "targetLabel": target_label,
                "crossBuilding": cross_building,
            }
        )

    if floor is None or building is None or world is None:
        floor, building, world = resolve_ancestors(session, location)
    if hub is None:
        hub = hub_root_node(session)

    node_ids = [int(n["id"]) for n in nodes if str(n["id"]).isdigit()]
    agents = _agents_near(session, node_ids)

    outdoor_room = is_outdoor_landmark_room(location)
    visible_nodes, visible_edges = _cap_room_focus_graph(
        nodes,
        edges,
        cap=int(DISPLAY_POLICY["maxMapNodesVisible"]),
    )
    payload: Dict[str, Any] = {
        "mode": "focus",
        "viewLayer": "room",
        "orientation": "north-up",
        "layout": "logical",
        "breadcrumb": _breadcrumb_chain(
            session,
            view_layer="room",
            hub=hub,
            world=world,
            building=None if outdoor_room else building,
            floor=None if outdoor_room else floor,
            room=location,
        ),
        "nodes": visible_nodes,
        "edges": visible_edges,
        "roomOccupants": _room_occupant_entries(
            occupants,
            selected_entity_id=selected_entity_id,
        ),
        "neighborLinks": _neighbor_links(session, location),
        "agentPresences": agents[: DISPLAY_POLICY["maxAgentsHighlighted"]],
        "highlightedPath": [visible_edges[0]["from"], visible_edges[0]["to"]] if visible_edges else [],
        "currentSpaceId": str(location.id),
        "selectedEntityId": selected_entity_id,
        "loading": False,
    }
    return _apply_mode_highlights(payload, mode)


def _default_floor_for_building(
    session: Session,
    building: Node,
    location: Node,
) -> Optional[Node]:
    """Default to the lowest floor (lobby / 首层) when entering a building."""
    _ = location
    floors = floors_in_building(session, building)
    if not floors:
        return None
    return floors[0]


def _floor_room_grid_extra(attrs: Dict[str, Any]) -> Dict[str, Any]:
    if not room_has_map_grid(attrs):
        return {}
    try:
        extra: Dict[str, Any] = {
            "mapGridCol": int(attrs["map_grid_col"]),
            "mapGridRow": int(attrs["map_grid_row"]),
            "mapGridSpanW": int(attrs.get("map_grid_span_w") or 1),
            "mapGridSpanH": int(attrs.get("map_grid_span_h") or 1),
        }
    except (TypeError, ValueError):
        return {}
    room_type = str(attrs.get("room_type") or "").strip()
    if room_type:
        extra["roomType"] = room_type
    return extra


def _floor_grid_bounds(rooms: List[Node]) -> Optional[Dict[str, int]]:
    extents: List[Tuple[int, int, int, int]] = []
    for room in rooms:
        attrs = dict(room.attributes or {})
        if not room_has_map_grid(attrs):
            continue
        try:
            col = int(attrs["map_grid_col"])
            row = int(attrs["map_grid_row"])
            span_w = int(attrs.get("map_grid_span_w") or 1)
            span_h = int(attrs.get("map_grid_span_h") or 1)
        except (TypeError, ValueError):
            continue
        extents.append((col, row, col + span_w, row + span_h))
    if not extents:
        return None
    return {
        "minCol": min(item[0] for item in extents),
        "minRow": min(item[1] for item in extents),
        "maxCol": max(item[2] for item in extents),
        "maxRow": max(item[3] for item in extents),
        "cellPx": MAP_GRID_CELL_PX,
        "originX": MAP_GRID_ORIGIN_X,
        "originY": MAP_GRID_ORIGIN_Y,
    }


def _floor_stack_entries(
    session: Session,
    building: Optional[Node],
    anchor_floor: Node,
    location: Node,
) -> List[Dict[str, Any]]:
    if building is None:
        return []
    player_floor, _, _ = resolve_ancestors(session, location)
    player_floor_id: Optional[int] = None
    if player_floor is not None and str(getattr(player_floor, "type_code", "")) == "building_floor":
        player_floor_id = int(player_floor.id)
    anchor_id = int(anchor_floor.id)
    entries: List[Dict[str, Any]] = []
    for fl in floors_in_building(session, building):
        fl_id = int(fl.id)
        if fl_id == anchor_id:
            status = "current" if player_floor_id == anchor_id else "active"
        elif player_floor_id is not None and fl_id == player_floor_id:
            status = "current"
        else:
            status = "visible"
        attrs = dict(fl.attributes or {})
        entry: Dict[str, Any] = {
            "id": str(fl.id),
            "name": _display_name(fl),
            "status": status,
        }
        floor_no = attrs.get("floor_number") or attrs.get("floor_no")
        if floor_no is not None:
            try:
                entry["floorNumber"] = int(floor_no)
            except (TypeError, ValueError):
                pass
        entries.append(entry)
    return entries


def _floor_display_rooms(
    rooms: List[Node],
    location: Node,
    *,
    max_visible: int,
) -> Tuple[List[Node], int]:
    """Pick rooms to render; return overflow count for optional cluster node."""
    if len(rooms) <= max_visible:
        return rooms, 0
    current_id = int(location.id)
    visible: List[Node] = []
    overflow = 0
    for room in rooms:
        if int(room.id) == current_id:
            if room not in visible:
                visible.insert(0, room)
            continue
        if len(visible) < max_visible - 1:
            visible.append(room)
        else:
            overflow += 1
    if overflow <= 0:
        return rooms[:max_visible], 0
    return visible, overflow


def _append_floor_plan_exit_nodes(
    session: Session,
    *,
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    floor: Node,
    map_anchor: Node,
    grid_room_ids: set[int],
    location: Node,
    selected_entity_id: Optional[str],
) -> None:
    """Add compass-positioned exit nodes for cross-building / off-floor ``look`` neighbors."""
    floor_rooms = rooms_on_floor(session, floor)
    floor_room_ids = {int(room.id) for room in floor_rooms}
    anchor_attrs = dict(map_anchor.attributes or {})
    if room_has_map_grid(anchor_attrs):
        anchor_x, anchor_y = grid_to_map_coords(
            int(anchor_attrs["map_grid_col"]),
            int(anchor_attrs["map_grid_row"]),
            span_w=int(anchor_attrs.get("map_grid_span_w") or 1),
            span_h=int(anchor_attrs.get("map_grid_span_h") or 1),
        )
    else:
        anchor_x, anchor_y = 50, 50

    existing_node_ids = {str(node["id"]) for node in nodes}
    existing_edge_pairs = {
        (str(edge.get("from") or ""), str(edge.get("to") or "")) for edge in edges
    }

    for row in floor_map_look_exits(session, map_anchor):
        target_id = int(row["target_id"])
        target = get_active_node(session, target_id)
        if not target:
            continue
        direction = str(row.get("direction") or "")
        display_node, cross_building, target_label = _resolve_exit_display_node(
            session,
            map_anchor,
            target,
            target_display_name=str(row.get("target_display_name") or ""),
        )
        display_id = str(display_node.id)

        on_floor_grid = target_id in grid_room_ids and str(target_id) in existing_node_ids
        if on_floor_grid and not cross_building:
            continue

        if display_id not in existing_node_ids:
            x, y = floor_grid_compass_position(anchor_x, anchor_y, direction)
            status = _node_status(
                display_node,
                current_space_id=str(location.id),
                selected_entity_id=selected_entity_id,
            )
            exit_extra: Dict[str, Any] = {"direction": direction, "floorExit": True}
            if cross_building:
                exit_extra["crossBuilding"] = True
            if int(display_node.id) != target_id:
                exit_extra["drillAnchorId"] = str(target_id)
            nodes.append(
                _map_node_payload(
                    display_node,
                    status,
                    x,
                    y,
                    extra=exit_extra,
                )
            )
            existing_node_ids.add(display_id)

        edge_pair = (str(map_anchor.id), display_id)
        if edge_pair in existing_edge_pairs:
            continue
        edge_status = "cross-building" if cross_building else "available"
        edges.append(
            {
                "id": f"floor_exit_{map_anchor.id}_{target_id}",
                "from": str(map_anchor.id),
                "to": display_id,
                "label": direction,
                "direction": direction,
                "status": edge_status,
                "targetLabel": target_label,
                "crossBuilding": cross_building,
            }
        )
        existing_edge_pairs.add(edge_pair)


def build_floor_focus_map(
    session: Session,
    location: Node,
    floor: Node,
    *,
    mode: str = "focus",
    selected_entity_id: Optional[str] = None,
    building: Optional[Node] = None,
    world: Optional[Node] = None,
    event_space_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    floor_rooms = rooms_on_floor(session, floor)
    map_anchor = resolve_floor_map_anchor(floor_rooms, location) or location
    all_rooms = rooms_for_floor_map(session, floor, location)
    max_visible = int(DISPLAY_POLICY["maxFloorNodesVisible"])
    rooms, overflow_count = _floor_display_rooms(all_rooms, location, max_visible=max_visible)
    room_id_list = [int(r.id) for r in all_rooms]
    grid_room_ids = set(room_id_list)
    has_grid = bool(all_rooms) and all(
        room_has_map_grid(dict(r.attributes or {})) for r in all_rooms
    )
    visible_ids = {int(r.id) for r in rooms}
    overflow_rooms = [r for r in all_rooms if int(r.id) not in visible_ids]

    if building is None or world is None:
        building = building or building_for_floor(session, floor)
        world = world or (world_for_building(session, building) if building else None)
        if building is None or world is None:
            _, building, world = resolve_ancestors(session, location)

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    layout = "grid" if has_grid else "list"

    if has_grid:
        for room in rooms:
            attrs = dict(room.attributes or {})
            if not room_has_map_grid(attrs):
                continue
            col = int(attrs["map_grid_col"])
            row = int(attrs["map_grid_row"])
            span_w = int(attrs.get("map_grid_span_w") or 1)
            span_h = int(attrs.get("map_grid_span_h") or 1)
            x, y = grid_to_map_coords(col, row, span_w=span_w, span_h=span_h)
            status = _node_status(room, current_space_id=str(location.id), selected_entity_id=selected_entity_id)
            nodes.append(_map_node_payload(room, status, x, y, extra=_floor_room_grid_extra(attrs)))
        for rel in _intra_floor_edges(session, room_id_list):
            direction = _edge_direction(rel, session.query(Node).filter(Node.id == rel.target_id).first() or rel)
            if direction in _VERTICAL_EDGE_DIRECTIONS:
                continue
            edge_status = "available"
            if direction in _VERTICAL_EDGE_DIRECTIONS:
                edge_status = "locked"
            edges.append(
                {
                    "id": str(rel.id),
                    "from": str(rel.source_id),
                    "to": str(rel.target_id),
                    "label": direction,
                    "direction": direction,
                    "status": edge_status,
                }
            )
        _append_floor_plan_exit_nodes(
            session,
            nodes=nodes,
            edges=edges,
            floor=floor,
            map_anchor=map_anchor,
            grid_room_ids=grid_room_ids,
            location=location,
            selected_entity_id=selected_entity_id,
        )
    floor_room_list: List[Dict[str, Any]] = []
    if not has_grid:
        layout = "list"
        for room in all_rooms:
            floor_room_list.append(
                {
                    "id": str(room.id),
                    "name": _display_name(room),
                    "status": _node_status(
                        room,
                        current_space_id=str(location.id),
                        selected_entity_id=selected_entity_id,
                    ),
                }
            )
    elif overflow_count > 0:
        cluster_x, cluster_y = 82, 50
        first_overflow = overflow_rooms[0] if overflow_rooms else None
        nodes.append(
            {
                "id": f"cluster:floor:{floor.id}",
                "name": f"+{overflow_count} rooms",
                "type": "cluster",
                "x": cluster_x,
                "y": cluster_y,
                "status": "visible",
                "semanticTags": ["cluster"],
                "activeAgentIds": [],
                "activeEventIds": [],
                "objectIds": [],
                "floorId": str(floor.id),
                "overflowCount": overflow_count,
                "drillAnchorId": str(first_overflow.id) if first_overflow else None,
            }
        )

    agents = _agents_near(session, room_id_list)
    hub = hub_root_node(session)
    floor_grid_bounds = _floor_grid_bounds(all_rooms) if has_grid else None
    floor_stack = _floor_stack_entries(session, building, floor, location)
    payload: Dict[str, Any] = {
        "mode": "focus",
        "viewLayer": "floor",
        "orientation": "north-up",
        "layout": layout,
        "floorPlanReady": has_grid,
        "floorGridBounds": floor_grid_bounds,
        "floorStack": floor_stack,
        "breadcrumb": _breadcrumb_chain(
            session,
            view_layer="floor",
            hub=hub,
            world=world,
            building=building,
            floor=floor,
        ),
        "nodes": nodes,
        "floorRoomList": floor_room_list,
        "edges": edges,
        "neighborLinks": [],
        "agentPresences": agents[: DISPLAY_POLICY["maxAgentsHighlighted"]],
        "highlightedPath": [],
        "currentSpaceId": str(location.id),
        "selectedEntityId": selected_entity_id,
        "loading": False,
    }
    if event_space_ids:
        payload["eventSpaceIds"] = list(event_space_ids)
    return _apply_mode_highlights(payload, mode)


def build_building_focus_map(
    session: Session,
    location: Node,
    building: Node,
    *,
    mode: str = "focus",
    selected_entity_id: Optional[str] = None,
    world: Optional[Node] = None,
) -> Dict[str, Any]:
    floors = floors_in_building(session, building)
    positions = vertical_stack_positions(len(floors), start_y=16, step=16)
    nodes: List[Dict[str, Any]] = []
    for index, floor in enumerate(floors):
        x, y = positions[index] if index < len(positions) else (50, 16 + index * 16)
        status = _node_status(floor, current_space_id=str(location.id), selected_entity_id=selected_entity_id)
        nodes.append(_map_node_payload(floor, status, x, y))

    if world is None:
        world = world_for_building(session, building)
    if world is None:
        _, _, world = resolve_ancestors(session, location)
    floor, _, _ = resolve_ancestors(session, location)
    hub = hub_root_node(session)

    payload: Dict[str, Any] = {
        "mode": "focus",
        "viewLayer": "building",
        "orientation": "north-up",
        "layout": "hierarchy",
        "breadcrumb": _breadcrumb_chain(
            session,
            view_layer="building",
            hub=hub,
            world=world,
            building=building,
        ),
        "nodes": nodes,
        "edges": [],
        "neighborLinks": [],
        "agentPresences": [],
        "highlightedPath": [],
        "currentSpaceId": str(location.id),
        "selectedEntityId": selected_entity_id,
        "loading": False,
    }
    return _apply_mode_highlights(payload, mode)


def _campus_node_position(
    node: Node,
    index: int,
    total: int,
    *,
    max_col: int = 24,
    max_row: int = 20,
) -> Tuple[int, int]:
    attrs = dict(node.attributes or {})
    col = attrs.get("campus_grid_col")
    row = attrs.get("campus_grid_row")
    if col is not None and row is not None:
        try:
            return campus_grid_position(int(col), int(row), max_col=max_col, max_row=max_row)
        except (TypeError, ValueError):
            pass
    positions = horizontal_row_positions(total)
    return positions[index] if index < len(positions) else (14 + index * 16, 50)


def build_campus_focus_map(
    session: Session,
    location: Node,
    world: Node,
    *,
    mode: str = "focus",
    selected_entity_id: Optional[str] = None,
) -> Dict[str, Any]:
    wid = str(dict(world.attributes or {}).get("world_id") or dict(world.attributes or {}).get("package_node_id") or "hicampus")
    buildings = buildings_in_world(session, wid)
    outdoors = outdoor_landmark_rooms(session, wid)
    entries: List[Node] = buildings + outdoors
    max_visible = DISPLAY_POLICY["maxCampusNodesVisible"]
    grid_cols = [
        int(dict(n.attributes or {}).get("campus_grid_col"))
        for n in entries
        if dict(n.attributes or {}).get("campus_grid_col") is not None
    ]
    grid_rows = [
        int(dict(n.attributes or {}).get("campus_grid_row"))
        for n in entries
        if dict(n.attributes or {}).get("campus_grid_row") is not None
    ]
    max_col = max(grid_cols) if grid_cols else 24
    max_row = max(grid_rows) if grid_rows else 20

    campus_spot: Optional[Node] = None
    if selected_entity_id and str(selected_entity_id).isdigit():
        spot = get_active_node(session, int(selected_entity_id))
        if spot and is_outdoor_landmark_room(spot):
            campus_spot = spot

    nodes: List[Dict[str, Any]] = []
    if len(entries) > max_visible:
        by_building: Dict[str, List[Node]] = {}
        for b in buildings:
            bid = str(dict(b.attributes or {}).get("package_node_id") or b.id)
            by_building.setdefault(bid, []).append(b)
        cluster_index = 0
        for bid, group in sorted(by_building.items()):
            anchor_building = group[0]
            x, y = _campus_node_position(
                anchor_building, cluster_index, len(by_building), max_col=max_col, max_row=max_row
            )
            cluster_index += 1
            nodes.append(
                {
                    "id": f"cluster:{bid}",
                    "name": f"+{len(group)} {_display_name(group[0])}",
                    "type": "cluster",
                    "x": x,
                    "y": y,
                    "status": "visible",
                    "semanticTags": ["cluster"],
                    "activeAgentIds": [],
                    "activeEventIds": [],
                    "objectIds": [],
                    "buildingId": bid,
                    "drillAnchorId": str(group[0].id),
                }
            )
        for index, outdoor in enumerate(outdoors[:6]):
            x, y = horizontal_row_positions(len(outdoors), y=62)[index] if index < len(outdoors) else (14 + index * 16, 62)
            status = _node_status(outdoor, current_space_id=str(location.id), selected_entity_id=selected_entity_id)
            nodes.append(_map_node_payload(outdoor, status, x, y))
    else:
        total = len(entries)
        for index, node in enumerate(entries):
            x, y = _campus_node_position(node, index, total, max_col=max_col, max_row=max_row)
            status = _node_status(node, current_space_id=str(location.id), selected_entity_id=selected_entity_id)
            nodes.append(_map_node_payload(node, status, x, y))

    hub = hub_root_node(session)
    has_campus_grid = all(
        dict(node.attributes or {}).get("campus_grid_col") is not None
        and dict(node.attributes or {}).get("campus_grid_row") is not None
        for node in entries
    )
    edges: List[Dict[str, Any]] = []
    outdoor_nodes = {int(node.id): node for node in outdoors}
    outdoor_ids = set(outdoor_nodes.keys())
    building_nodes_by_id = {int(node.id): node for node in buildings}
    seen_edge_pairs: set[Tuple[str, str]] = set()

    def _campus_endpoint_id(node: Optional[Node]) -> Optional[str]:
        if not node:
            return None
        if str(node.type_code) == "building":
            return str(node.id)
        if int(node.id) in outdoor_ids:
            return str(node.id)
        _, building, _ = resolve_ancestors(session, node)
        return str(building.id) if building else None

    def _append_campus_edge(rel: Relationship, source_node: Node, target_node: Node) -> None:
        src_id = _campus_endpoint_id(source_node)
        tgt_id = _campus_endpoint_id(target_node)
        if not src_id or not tgt_id or src_id == tgt_id:
            return
        pair = (src_id, tgt_id)
        if pair in seen_edge_pairs:
            return
        seen_edge_pairs.add(pair)
        direction = _edge_direction(rel, target_node)
        edges.append(
            {
                "id": str(rel.id),
                "from": src_id,
                "to": tgt_id,
                "label": direction,
                "direction": direction,
                "status": "available",
                "targetLabel": _display_name(target_node),
            }
        )

    for rel in outdoor_landmark_edges(session, wid):
        source = outdoor_nodes.get(rel.source_id)
        target = outdoor_nodes.get(rel.target_id)
        if source and target:
            _append_campus_edge(rel, source, target)

    connector_rooms = list(outdoors)
    inter_rels = campus_inter_building_edges(
        session,
        wid,
        building_nodes=buildings,
        connector_nodes=connector_rooms,
    )
    inter_endpoint_ids = {
        int(rel_id)
        for rel in inter_rels
        for rel_id in (rel.source_id, rel.target_id)
    }
    inter_nodes = (
        session.query(Node)
        .filter(Node.id.in_(inter_endpoint_ids), Node.is_active == True)
        .all()
        if inter_endpoint_ids
        else []
    )
    inter_node_by_id = {int(node.id): node for node in inter_nodes}
    for rel in inter_rels:
        source = inter_node_by_id.get(int(rel.source_id))
        target = inter_node_by_id.get(int(rel.target_id))
        if source and target:
            _append_campus_edge(rel, source, target)

    payload: Dict[str, Any] = {
        "mode": "focus",
        "viewLayer": "campus",
        "orientation": "north-up",
        "layout": "grid" if has_campus_grid and len(entries) <= max_visible else "hierarchy",
        "breadcrumb": _breadcrumb_chain(
            session,
            view_layer="campus",
            hub=hub,
            world=world,
            campus_spot=campus_spot,
        ),
        "nodes": nodes,
        "edges": edges,
        "neighborLinks": [],
        "agentPresences": [],
        "highlightedPath": [],
        "currentSpaceId": str(location.id),
        "selectedEntityId": selected_entity_id,
        "loading": False,
    }
    return _apply_mode_highlights(payload, mode)


def build_world_focus_map(
    session: Session,
    location: Node,
    *,
    mode: str = "focus",
    selected_entity_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Multi-world hub map: worlds, portal rooms, and inter-world connector edges."""
    hub, world_nodes, entrances = world_map_entries(session)
    _, _, current_world = resolve_ancestors(session, location)
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    hub_is_current = hub is not None and int(location.id) == int(hub.id)
    if hub:
        nodes.append(
            _map_node_payload(
                hub,
                "current" if hub_is_current else "visible",
                50,
                50,
                extra={"logicalZone": "hub"},
            )
        )

    entrance_by_world: Dict[str, Node] = {}
    for ent in entrances:
        attrs = dict(ent.attributes or {})
        wid = str(attrs.get("portal_world_id") or attrs.get("world_id") or ent.name or "").strip().lower()
        if wid:
            entrance_by_world[wid] = ent

    world_entries = world_nodes if world_nodes else list(entrances)
    world_id_by_pkg: Dict[str, str] = {}
    for wnode in world_nodes:
        attrs = dict(wnode.attributes or {})
        wid = str(attrs.get("world_id") or wnode.name or "").strip().lower()
        if wid:
            world_id_by_pkg[wid] = str(wnode.id)

    world_positions = horizontal_row_positions(len(world_entries), y=28, start_x=12, step=18)
    for index, wnode in enumerate(world_entries):
        x, y = world_positions[index] if index < len(world_positions) else (12 + index * 18, 28)
        status = "visible"
        if current_world and int(wnode.id) == int(current_world.id):
            status = "current"
        elif selected_entity_id and str(wnode.id) == str(selected_entity_id):
            status = "active"
        nodes.append(_map_node_payload(wnode, status, x, y))

    entrance_positions = horizontal_row_positions(len(entrances), y=72, start_x=12, step=16)
    for index, ent in enumerate(entrances):
        x, y = entrance_positions[index] if index < len(entrance_positions) else (12 + index * 16, 72)
        attrs = dict(ent.attributes or {})
        wid = str(attrs.get("portal_world_id") or attrs.get("world_id") or ent.name or "").strip().lower()
        drill_id = world_id_by_pkg.get(wid)
        extra = {"drillAnchorId": drill_id} if drill_id else None
        nodes.append(_map_node_payload(ent, "visible", x, y, extra=extra))

    if hub:
        for ent in entrances:
            edges.append(
                {
                    "id": f"portal_{hub.id}_{ent.id}",
                    "from": str(hub.id),
                    "to": str(ent.id),
                    "label": "portal",
                    "status": "available",
                    "targetLabel": _display_name(ent),
                }
            )

    for wnode in world_entries:
        attrs = dict(wnode.attributes or {})
        wid = str(attrs.get("world_id") or wnode.name or "").strip().lower()
        ent = entrance_by_world.get(wid)
        if ent:
            edges.append(
                {
                    "id": f"enter_{ent.id}_{wnode.id}",
                    "from": str(ent.id),
                    "to": str(wnode.id),
                    "label": "enter",
                    "status": "recommended",
                    "targetLabel": _display_name(wnode),
                }
            )

    if len(entrances) >= 2:
        ent_ids = [int(node.id) for node in entrances]
        rels = (
            session.query(Relationship)
            .filter(
                Relationship.type_code == "connects_to",
                Relationship.is_active == True,
                Relationship.source_id.in_(ent_ids),
            )
            .all()
        )
        ent_id_set = set(ent_ids)
        for rel in rels:
            if rel.target_id not in ent_id_set:
                continue
            target = get_active_node(session, int(rel.target_id))
            source = get_active_node(session, int(rel.source_id))
            if not source or not target:
                continue
            edges.append(
                {
                    "id": str(rel.id),
                    "from": str(rel.source_id),
                    "to": str(rel.target_id),
                    "label": _edge_direction(rel, target),
                    "direction": _edge_direction(rel, target),
                    "status": "available",
                    "targetLabel": _display_name(target),
                }
            )

    payload: Dict[str, Any] = {
        "mode": "focus",
        "viewLayer": "world",
        "orientation": "north-up",
        "layout": "hierarchy",
        "breadcrumb": _breadcrumb_chain(session, view_layer="world", hub=hub),
        "nodes": nodes[: int(DISPLAY_POLICY.get("maxWorldNodesVisible", 24))],
        "edges": edges,
        "neighborLinks": [],
        "agentPresences": [],
        "highlightedPath": [],
        "currentSpaceId": str(location.id),
        "selectedEntityId": selected_entity_id,
        "loading": False,
    }
    return _apply_mode_highlights(payload, mode)


def apply_event_space_ids(focus_map: Dict[str, Any], event_space_ids: List[str]) -> Dict[str, Any]:
    """Attach decision-event space ids and apply event-mode highlights."""
    payload = dict(focus_map)
    payload["eventSpaceIds"] = [str(i) for i in event_space_ids if str(i)]
    return _apply_mode_highlights(payload, "event")


def build_focus_map(
    session: Session,
    location: Node,
    *,
    view_layer: str = "room",
    anchor_id: Optional[str] = None,
    mode: str = "focus",
    selected_entity_id: Optional[str] = None,
    event_space_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    layer = str(view_layer or "room").strip().lower()
    if layer not in VIEW_LAYERS:
        layer = "room"
    selected = selected_entity_id or None
    player_floor, player_building, player_world = resolve_ancestors(session, location)
    hub = hub_root_node(session)

    if layer == "world":
        payload = build_world_focus_map(
            session,
            location,
            mode=mode,
            selected_entity_id=selected,
        )
        if event_space_ids and mode == "event":
            return apply_event_space_ids(payload, event_space_ids)
        return payload

    if layer == "room":
        target = location
        if anchor_id and str(anchor_id).isdigit():
            anchor_room = get_active_node(session, int(anchor_id))
            if anchor_room and str(anchor_room.type_code) == "room":
                target = anchor_room
        ctx_floor, ctx_building, ctx_world = resolve_ancestors(session, target)
        payload = build_room_focus_map(
            session,
            target,
            mode=mode,
            selected_entity_id=selected,
            floor=ctx_floor,
            building=ctx_building,
            world=ctx_world,
            hub=hub,
        )
        if event_space_ids and mode == "event":
            return apply_event_space_ids(payload, event_space_ids)
        return payload

    anchor = resolve_anchor_node(session, view_layer=layer, anchor_id=anchor_id, location=location)
    if layer == "floor" and anchor and str(anchor.type_code) == "building_floor":
        ctx_building = building_for_floor(session, anchor)
        ctx_world = world_for_building(session, ctx_building) if ctx_building else player_world
        payload = build_floor_focus_map(
            session,
            location,
            anchor,
            mode=mode,
            selected_entity_id=selected,
            building=ctx_building,
            world=ctx_world,
            event_space_ids=event_space_ids,
        )
        if event_space_ids and mode == "event":
            return apply_event_space_ids(payload, event_space_ids)
        return payload
    if layer == "building" and anchor and str(anchor.type_code) == "building":
        default_floor = _default_floor_for_building(session, anchor, location)
        if default_floor is not None:
            ctx_building = anchor
            ctx_world = world_for_building(session, anchor) or player_world
            payload = build_floor_focus_map(
                session,
                location,
                default_floor,
                mode=mode,
                selected_entity_id=selected,
                building=ctx_building,
                world=ctx_world,
                event_space_ids=event_space_ids,
            )
            if event_space_ids and mode == "event":
                return apply_event_space_ids(payload, event_space_ids)
            return payload
        ctx_world = world_for_building(session, anchor) or player_world
        payload = build_building_focus_map(
            session,
            location,
            anchor,
            mode=mode,
            selected_entity_id=selected,
            world=ctx_world,
        )
        if event_space_ids and mode == "event":
            return apply_event_space_ids(payload, event_space_ids)
        return payload
    if layer == "campus":
        campus_world = player_world
        if anchor and str(getattr(anchor, "type_code", "")) == "world":
            campus_world = anchor
        if campus_world:
            payload = build_campus_focus_map(
                session,
                location,
                campus_world,
                mode=mode,
                selected_entity_id=selected,
            )
            if event_space_ids and mode == "event":
                return apply_event_space_ids(payload, event_space_ids)
            return payload

    payload = build_room_focus_map(
        session,
        location,
        mode=mode,
        selected_entity_id=selected,
        floor=player_floor,
        building=player_building,
        world=player_world,
    )
    if event_space_ids and mode == "event":
        return apply_event_space_ids(payload, event_space_ids)
    return payload


def apply_highlight_ids_to_focus_map(
    focus_map: Dict[str, Any],
    highlighted_ids: List[str],
    *,
    mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply query/search highlights onto an existing focus_map payload."""
    payload = dict(focus_map)
    ids = {str(i) for i in highlighted_ids if str(i)}
    nodes = []
    for node in list(payload.get("nodes") or []):
        n = dict(node)
        nid = str(n.get("id"))
        if nid in ids:
            n["status"] = "active" if nid != str(payload.get("currentSpaceId")) else "current"
        nodes.append(n)
    payload["nodes"] = nodes
    if ids:
        payload["selectedEntityId"] = next(iter(ids))
    if mode:
        payload = _apply_mode_highlights(payload, mode)
    return payload


def build_map_query_patch(
    session: Session,
    search_results: List[Dict[str, Any]],
    query: str,
    *,
    mode: str = "auto",
) -> Dict[str, Any]:
    """Build map_patch for semantic-map query from world-search results."""
    clean_mode = mode if mode in MAP_MODES else "auto"
    highlighted: List[str] = []
    view_layer: Optional[str] = None
    anchor_id: Optional[str] = None

    for item in search_results:
        entity_id = str(item.get("entity_id") or "")
        entity_type = str(item.get("entity_type") or "")
        if entity_type not in {"space", "agent"} or not entity_id.isdigit():
            continue
        highlighted.append(entity_id)
        node = get_active_node(session, int(entity_id))
        if not node:
            continue
        tc = str(node.type_code or "")
        if tc == "building":
            view_layer = "campus"
        elif tc == "building_floor" and view_layer != "campus":
            view_layer = "floor"
            anchor_id = str(node.id)
        elif tc == "room":
            if is_outdoor_landmark_room(node):
                view_layer = "campus"
            elif view_layer not in {"campus", "floor"} and node.location_id:
                view_layer = "floor"
                anchor_id = str(node.location_id)

    lowered = str(query or "").lower()
    if clean_mode == "auto":
        map_mode = "agent" if "agent" in lowered or any(r.get("entity_type") == "agent" for r in search_results) else "focus"
        if "route" in lowered:
            map_mode = "route"
        if "event" in lowered:
            map_mode = "event"
    else:
        map_mode = clean_mode

    patch: Dict[str, Any] = {
        "mode": map_mode,
        "highlightedNodeIds": highlighted[: DISPLAY_POLICY["maxCampusNodesVisible"]],
    }
    if view_layer:
        patch["viewLayer"] = view_layer
    if anchor_id:
        patch["anchorId"] = anchor_id
    return patch
