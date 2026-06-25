"""Structured entity inspect payloads for semantic map (look/space SSOT)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from app.commands.base import CommandContext
from app.commands.game.look_command import LookCommand
from app.commands.space_command import _node_space_trait
from app.models.graph import Node
from app.services.world_interaction.types import WorldActor


def _display_name(node: Optional[Node]) -> str:
    if not node:
        return "Unknown"
    attrs = dict(node.attributes or {})
    type_code = str(node.type_code or "")
    if type_code == "building_floor":
        return str(attrs.get("display_name") or attrs.get("floor_name") or attrs.get("name") or node.name)
    if type_code == "building":
        return str(attrs.get("display_name") or attrs.get("building_name") or attrs.get("name") or node.name)
    return str(attrs.get("display_name") or attrs.get("room_name") or attrs.get("name") or node.name)


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
        return "room"
    trait = str(getattr(node, "trait_class", "") or "").upper()
    if trait == "DEVICE":
        return "device"
    if trait == "ITEM":
        return "object"
    if type_code == "npc_agent":
        return "agent"
    if type_code == "account":
        return "service"
    if trait in {"AGENT", "PERSON"} and type_code != "npc_agent":
        return "service"
    return "service"



def _is_person_node(node: Node) -> bool:
    """Align with space §2 occupants: account/character/PERSON, not npc_agent."""
    type_code = str(node.type_code or "").lower()
    trait = str(getattr(node, "trait_class", "") or "").upper()
    attrs = dict(node.attributes or {})
    entity_kind_attr = str(attrs.get("entity_kind") or "").lower()
    if type_code == "npc_agent":
        return False
    if type_code in {"account", "character", "user"}:
        return True
    if entity_kind_attr == "character":
        return True
    if trait in {"PERSON", "AGENT"}:
        return True
    return False


def _entity_kind(node: Node, map_node_type: str) -> str:
    type_code = str(node.type_code or "").lower()
    trait = str(getattr(node, "trait_class", "") or "").upper()
    if type_code == "npc_agent":
        return "agent"
    if _is_person_node(node):
        return "person"
    if trait == "DEVICE" or map_node_type == "device":
        return "device"
    if trait == "ITEM" or map_node_type == "object":
        return "object"
    return "object"


def _build_context(session: Any, actor: WorldActor) -> CommandContext:
    return CommandContext(
        user_id=actor.user_id,
        username=actor.username,
        session_id=f"inspect_{actor.user_id}",
        permissions=list(actor.permissions or []),
        roles=list(actor.roles or []),
        db_session=session,
    )


def _node_object_dict(node: Node) -> Dict[str, Any]:
    return {
        "id": str(node.id),
        "name": node.name,
        "node_id": node.id,
        "type_code": node.type_code,
        "type": node.type_code,
        "description": node.description,
        "attributes": dict(node.attributes or {}),
    }


def _parse_status_lines(text: str) -> List[Dict[str, str]]:
    status: List[Dict[str, str]] = []
    for line in text.splitlines():
        clean = line.strip()
        if clean.startswith("状态:"):
            status.append({"label": "Status", "value": clean.split(":", 1)[1].strip()})
        elif clean.startswith("属性:"):
            status.append({"label": "Attributes", "value": clean.split(":", 1)[1].strip()})
    return status


def _actions_from_attributes(attrs: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = attrs.get("inspect_capabilities") or attrs.get("capabilities")
    if not isinstance(raw, list):
        return []
    actions: List[Dict[str, Any]] = []
    for index, item in enumerate(raw[:3]):
        if not isinstance(item, dict):
            continue
        action_id = str(item.get("id") or f"cap_{index}")
        label = str(item.get("label") or "Action")
        style = str(item.get("style") or "secondary")
        action_type = str(item.get("actionType") or item.get("action_type") or "execute_command")
        command = item.get("command")
        target = item.get("targetEntityId") or item.get("target_entity_id")
        requires = bool(item.get("requiresConfirmation") or item.get("requires_confirmation"))
        actions.append(
            {
                "id": action_id,
                "label": label,
                "style": style,
                "actionType": action_type,
                "command": command,
                "targetEntityId": str(target) if target is not None else None,
                "requiresConfirmation": requires,
            }
        )
    return actions


_INSPECT_SKIP_LINE_PREFIXES = (
    "引用:",
    "包内节点:",
    "节点 id:",
)


def _filter_inspect_appearance_lines(lines: List[str]) -> List[str]:
    """Drop look tail metadata that is useful in SSH but confusing in map inspect."""
    filtered: List[str] = []
    for line in lines:
        clean = line.strip()
        if not clean:
            continue
        if any(clean.startswith(prefix) for prefix in _INSPECT_SKIP_LINE_PREFIXES):
            continue
        filtered.append(clean)
    return filtered


def _resolve_node_id(*, node_id: Optional[int], agent_id: Optional[str]) -> Optional[int]:
    if node_id is not None:
        return int(node_id)
    clean = str(agent_id or "").strip()
    if clean.isdigit():
        return int(clean)
    return None


def visible_node_ids_from_focus_map(focus_map: Optional[Dict[str, Any]]) -> Set[int]:
    """Collect graph node ids currently represented on the semantic map."""
    if not focus_map:
        return set()
    ids: Set[int] = set()
    for node in focus_map.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        raw = str(node.get("id") or "")
        if raw.isdigit():
            ids.add(int(raw))
        for oid in node.get("objectIds") or []:
            if str(oid).isdigit():
                ids.add(int(oid))
        for aid in node.get("activeAgentIds") or []:
            if str(aid).isdigit():
                ids.add(int(aid))
    for agent in focus_map.get("agentPresences") or []:
        if not isinstance(agent, dict):
            continue
        raw = str(agent.get("agentId") or "")
        if raw.isdigit():
            ids.add(int(raw))
    for occupant in focus_map.get("roomOccupants") or []:
        if not isinstance(occupant, dict):
            continue
        raw = str(occupant.get("id") or "")
        if raw.isdigit():
            ids.add(int(raw))
    selected = focus_map.get("selectedEntityId")
    if selected and str(selected).isdigit():
        ids.add(int(selected))
    return ids


def _can_inspect_node(
    session: Any,
    user_node: Optional[Node],
    node: Node,
    *,
    visible_node_ids: Optional[Set[int]] = None,
) -> bool:
    if user_node is None:
        return False
    if int(node.id) == int(user_node.id):
        return True
    if _node_space_trait(session, node):
        return True
    if user_node.location_id and node.location_id and int(node.location_id) == int(user_node.location_id):
        return True
    if user_node.location_id and int(node.id) == int(user_node.location_id):
        return True
    if visible_node_ids and int(node.id) in visible_node_ids:
        return True
    return False


def build_entity_inspect_data(
    session: Any,
    actor: WorldActor,
    *,
    node_id: Optional[int] = None,
    agent_id: Optional[str] = None,
    visible_node_ids: Optional[Set[int]] = None,
) -> Optional[Dict[str, Any]]:
    """Return structured inspect payload for non-space nodes."""
    resolved_id = _resolve_node_id(node_id=node_id, agent_id=agent_id)
    if resolved_id is None:
        return None

    node = session.query(Node).filter(Node.id == int(resolved_id), Node.is_active == True).first()
    if node is None or _node_space_trait(session, node):
        return None

    user_node = (
        session.query(Node)
        .filter(Node.id == int(actor.user_id), Node.type_code == "account", Node.is_active == True)
        .first()
    )
    if not _can_inspect_node(session, user_node, node, visible_node_ids=visible_node_ids):
        return None

    map_node_type = _map_node_type(node)
    kind = _entity_kind(node, map_node_type)
    context = _build_context(session, actor)
    look_cmd = LookCommand()
    obj = look_cmd._graph_object_dict_by_node_id(context, int(node.id))
    if obj is None:
        obj = _node_object_dict(node)

    appearance_text = look_cmd._build_object_description(context, obj)
    status = _parse_status_lines(appearance_text)
    body_lines = _filter_inspect_appearance_lines(
        [
            line.strip()
            for line in appearance_text.splitlines()
            if line.strip() and not line.strip().startswith(("状态:", "属性:"))
        ]
    )

    attrs = dict(node.attributes or {})
    location: Optional[Dict[str, str]] = None
    if node.location_id:
        loc_node = session.query(Node).filter(Node.id == int(node.location_id), Node.is_active == True).first()
        if loc_node is not None:
            location = {"id": str(loc_node.id), "name": _display_name(loc_node)}

    return {
        "entity": {
            "id": str(node.id),
            "name": _display_name(node),
            "type_code": str(node.type_code or ""),
            "map_node_type": map_node_type,
        },
        "entity_kind": kind,
        "appearance": {"lines": body_lines},
        "status": status or None,
        "location": location,
        "actions": _actions_from_attributes(attrs),
        "source": "look",
    }
