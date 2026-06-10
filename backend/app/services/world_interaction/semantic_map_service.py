"""Semantic map focus graph builder for world interaction UI."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.commands.room_connects_to_query import connects_to_exits_from_room
from app.game_engine.direction_util import normalize_direction
from app.models.graph import Node, Relationship

from .map_geometry import grid_to_map_coords, room_has_map_grid
from .map_layer_queries import (
    OUTDOOR_LANDMARK_PACKAGE_IDS,
    buildings_in_world,
    floors_in_building,
    get_active_node,
    outdoor_landmark_edges,
    outdoor_landmark_rooms,
    resolve_anchor_node,
    resolve_ancestors,
    rooms_on_floor,
)
from .map_layout import (
    assign_neighbor_positions,
    campus_grid_position,
    horizontal_row_positions,
    vertical_stack_positions,
)
from .types import DISPLAY_POLICY

VIEW_LAYERS = frozenset({"room", "floor", "building", "campus"})
MAP_MODES = frozenset({"focus", "route", "agent", "event"})
_VERTICAL_EDGE_DIRECTIONS = frozenset({"up", "down"})


def _display_name(node: Optional[Node]) -> str:
    if not node:
        return "Unknown"
    attrs = dict(node.attributes or {})
    return str(attrs.get("display_name") or attrs.get("room_name") or attrs.get("name") or node.name)


def _map_node_type(node: Node) -> str:
    type_code = str(node.type_code or "")
    if type_code == "building_floor":
        return "floor"
    if "building" in type_code:
        return "building"
    if "room" in type_code:
        return "room"
    attrs = dict(node.attributes or {})
    tags = [str(t).lower() for t in (node.tags or [])]
    if "environment:outdoor" in tags or str(attrs.get("room_type") or "") == "circulation":
        return "outdoor"
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
    location: Node,
    *,
    floor: Optional[Node] = None,
    building: Optional[Node] = None,
    world: Optional[Node] = None,
    view_layer: str = "room",
) -> List[Dict[str, str]]:
    crumbs: List[Dict[str, str]] = []
    if world and view_layer in {"campus", "building", "floor", "room"}:
        crumbs.append({"layer": "campus", "id": str(world.id), "name": _display_name(world)})
    if building and view_layer in {"building", "floor", "room"}:
        crumbs.append({"layer": "building", "id": str(building.id), "name": _display_name(building)})
    if floor and view_layer in {"floor", "room"}:
        crumbs.append({"layer": "floor", "id": str(floor.id), "name": _display_name(floor)})
    if view_layer == "room":
        crumbs.append({"layer": "room", "id": str(location.id), "name": _display_name(location)})
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


def build_room_focus_map(
    session: Session,
    location: Node,
    *,
    mode: str = "focus",
    selected_entity_id: Optional[str] = None,
    floor: Optional[Node] = None,
    building: Optional[Node] = None,
    world: Optional[Node] = None,
) -> Dict[str, Any]:
    """Build focus-map payload for the room (neighbor) view layer."""
    rels = (
        session.query(Relationship)
        .filter(
            Relationship.source_id == location.id,
            Relationship.type_code == "connects_to",
            Relationship.is_active == True,
        )
        .limit(12)
        .all()
    )
    max_neighbors = DISPLAY_POLICY["maxMapNodesVisible"] - 1
    neighbor_rels = rels[:max_neighbors]
    target_ids = [rel.target_id for rel in neighbor_rels]
    targets = (
        {node.id: node for node in session.query(Node).filter(Node.id.in_(target_ids)).all()}
        if target_ids
        else {}
    )

    neighbor_entries: List[Tuple[str, str]] = []
    for rel in neighbor_rels:
        target = targets.get(rel.target_id)
        if not target:
            continue
        neighbor_entries.append((_edge_direction(rel, target), str(target.id)))

    positions = assign_neighbor_positions(neighbor_entries)
    nodes = [_map_node_payload(location, "current", 50, 50)]
    for index, rel in enumerate(neighbor_rels):
        target = targets.get(rel.target_id)
        if not target:
            continue
        x, y = positions[index] if index < len(positions) else (50, 22)
        status = _node_status(target, current_space_id=str(location.id), selected_entity_id=selected_entity_id)
        nodes.append(_map_node_payload(target, status, x, y))

    node_ids = [int(n["id"]) for n in nodes if str(n["id"]).isdigit()]
    agents = _agents_near(session, node_ids)
    edges: List[Dict[str, Any]] = []
    for index, rel in enumerate(neighbor_rels):
        target = targets.get(rel.target_id)
        if not target:
            continue
        direction = _edge_direction(rel, target)
        edges.append(
            {
                "id": str(rel.id),
                "from": str(rel.source_id),
                "to": str(rel.target_id),
                "label": direction,
                "direction": direction,
                "status": "recommended" if index == 0 else "available",
                "targetLabel": _display_name(target),
            }
        )

    if floor is None or building is None or world is None:
        floor, building, world = resolve_ancestors(session, location)

    payload: Dict[str, Any] = {
        "mode": "focus",
        "viewLayer": "room",
        "orientation": "north-up",
        "layout": "compass",
        "breadcrumb": _breadcrumb_chain(location, floor=floor, building=building, world=world, view_layer="room"),
        "nodes": nodes[: DISPLAY_POLICY["maxMapNodesVisible"]],
        "edges": edges,
        "neighborLinks": _neighbor_links(session, location),
        "agentPresences": agents[: DISPLAY_POLICY["maxAgentsHighlighted"]],
        "highlightedPath": [edges[0]["from"], edges[0]["to"]] if edges else [],
        "currentSpaceId": str(location.id),
        "selectedEntityId": selected_entity_id,
        "loading": False,
    }
    return _apply_mode_highlights(payload, mode)


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
    all_rooms = rooms_on_floor(session, floor)
    max_visible = int(DISPLAY_POLICY["maxFloorNodesVisible"])
    rooms, overflow_count = _floor_display_rooms(all_rooms, location, max_visible=max_visible)
    room_id_list = [int(r.id) for r in all_rooms]
    has_grid = bool(all_rooms) and all(
        room_has_map_grid(dict(r.attributes or {})) for r in all_rooms
    )
    visible_ids = {int(r.id) for r in rooms}
    overflow_rooms = [r for r in all_rooms if int(r.id) not in visible_ids]

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
            nodes.append(_map_node_payload(room, status, x, y))
        for rel in _intra_floor_edges(session, room_id_list):
            direction = _edge_direction(rel, session.query(Node).filter(Node.id == rel.target_id).first() or rel)
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
    payload: Dict[str, Any] = {
        "mode": "focus",
        "viewLayer": "floor",
        "orientation": "north-up",
        "layout": layout,
        "floorPlanReady": has_grid,
        "breadcrumb": _breadcrumb_chain(location, floor=floor, building=building, world=world, view_layer="floor"),
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
        _, _, world = resolve_ancestors(session, location)
    floor, _, _ = resolve_ancestors(session, location)

    payload: Dict[str, Any] = {
        "mode": "focus",
        "viewLayer": "building",
        "orientation": "north-up",
        "layout": "hierarchy",
        "breadcrumb": _breadcrumb_chain(location, floor=floor, building=building, world=world, view_layer="building"),
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


def _campus_node_position(node: Node, index: int, total: int) -> Tuple[int, int]:
    attrs = dict(node.attributes or {})
    col = attrs.get("campus_grid_col")
    row = attrs.get("campus_grid_row")
    if col is not None and row is not None:
        try:
            return campus_grid_position(int(col), int(row))
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

    nodes: List[Dict[str, Any]] = []
    if len(entries) > max_visible:
        by_building: Dict[str, List[Node]] = {}
        for b in buildings:
            bid = str(dict(b.attributes or {}).get("package_node_id") or b.id)
            by_building.setdefault(bid, []).append(b)
        cluster_index = 0
        for bid, group in sorted(by_building.items()):
            anchor_building = group[0]
            x, y = _campus_node_position(anchor_building, cluster_index, len(by_building))
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
            x, y = _campus_node_position(node, index, total)
            status = _node_status(node, current_space_id=str(location.id), selected_entity_id=selected_entity_id)
            nodes.append(_map_node_payload(node, status, x, y))

    floor, building, _ = resolve_ancestors(session, location)
    has_campus_grid = all(
        dict(node.attributes or {}).get("campus_grid_col") is not None
        and dict(node.attributes or {}).get("campus_grid_row") is not None
        for node in entries
    )
    edges: List[Dict[str, Any]] = []
    outdoor_nodes = {int(node.id): node for node in outdoors}
    for rel in outdoor_landmark_edges(session, wid):
        target = outdoor_nodes.get(rel.target_id)
        if not target:
            continue
        direction = _edge_direction(rel, target)
        edges.append(
            {
                "id": str(rel.id),
                "from": str(rel.source_id),
                "to": str(rel.target_id),
                "label": direction,
                "direction": direction,
                "status": "available",
                "targetLabel": _display_name(target),
            }
        )
    payload: Dict[str, Any] = {
        "mode": "focus",
        "viewLayer": "campus",
        "orientation": "north-up",
        "layout": "grid" if has_campus_grid and len(entries) <= max_visible else "hierarchy",
        "breadcrumb": _breadcrumb_chain(location, floor=floor, building=building, world=world, view_layer="campus"),
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
    floor, building, world = resolve_ancestors(session, location)

    if layer == "room":
        payload = build_room_focus_map(
            session,
            location,
            mode=mode,
            selected_entity_id=selected,
            floor=floor,
            building=building,
            world=world,
        )
        if event_space_ids and mode == "event":
            return apply_event_space_ids(payload, event_space_ids)
        return payload

    anchor = resolve_anchor_node(session, view_layer=layer, anchor_id=anchor_id, location=location)
    if layer == "floor" and anchor and str(anchor.type_code) == "building_floor":
        payload = build_floor_focus_map(
            session,
            location,
            anchor,
            mode=mode,
            selected_entity_id=selected,
            building=building,
            world=world,
            event_space_ids=event_space_ids,
        )
        if event_space_ids and mode == "event":
            return apply_event_space_ids(payload, event_space_ids)
        return payload
    if layer == "building" and anchor and str(anchor.type_code) == "building":
        payload = build_building_focus_map(
            session,
            location,
            anchor,
            mode=mode,
            selected_entity_id=selected,
            world=world,
        )
        if event_space_ids and mode == "event":
            return apply_event_space_ids(payload, event_space_ids)
        return payload
    if layer == "campus" and world:
        payload = build_campus_focus_map(
            session,
            location,
            world,
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
        floor=floor,
        building=building,
        world=world,
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
            attrs = dict(node.attributes or {})
            pkg = str(attrs.get("package_node_id") or "")
            tags = [str(t).lower() for t in (node.tags or [])]
            if pkg in OUTDOOR_LANDMARK_PACKAGE_IDS or "environment:outdoor" in tags:
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
