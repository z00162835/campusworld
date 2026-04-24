"""Context assembly for npc_agent LLM ticks (world snapshot, tool manifest).

Static system primer text lives in :mod:`app.game_engine.agent_runtime.system_primer_context`
and is surfaced by the ``primer`` command — it is not imported here to avoid
coupling this module to primer-only concerns.

Public builders here:

* :func:`build_world_snapshot` — per-tick dynamic facts for the Plan user turn.
* :func:`build_world_snapshot_from_session` — convenience wrapper with shallow DB reads.
* :func:`build_llm_tool_manifest` — dual-form tool manifest for native and JSON channels.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.game_engine.agent_runtime.tool_calling import ToolSchema, tool_schemas_from_surface
from app.game_engine.agent_runtime.world_runtime_queries import installed_worlds_from_session


@dataclass
class WorldSnapshotInputs:
    caller_username: Optional[str] = None
    caller_roles: Sequence[str] = ()
    caller_location_name: Optional[str] = None
    caller_location_short_desc: Optional[str] = None
    caller_active_world: Optional[str] = None
    caller_world_location: Optional[str] = None
    visible_exits: Sequence[str] = ()
    same_room_entities: Sequence[str] = ()
    installed_worlds: Sequence[Tuple[str, str]] = ()  # (world_id, root_room_name)
    tool_surface_count: int = 0
    recent_commands: Sequence[Tuple[str, str]] = ()  # (cmd_line, top_line_result)


def build_world_snapshot(inputs: WorldSnapshotInputs) -> str:
    lines: List[str] = ["Caller:"]
    lines.append(f"  identity: {inputs.caller_username or '(unknown)'}")
    if inputs.caller_roles:
        lines.append(f"  roles: {', '.join(sorted(inputs.caller_roles))}")
    lines.append(f"  location: {inputs.caller_location_name or '(unknown)'}")
    if inputs.caller_location_short_desc:
        lines.append(f"  location_desc: {inputs.caller_location_short_desc}")
    if inputs.caller_active_world:
        lines.append(f"  active_world: {inputs.caller_active_world}")
    if inputs.caller_world_location:
        lines.append(f"  world_location: {inputs.caller_world_location}")
    if inputs.visible_exits:
        lines.append(f"  exits: {', '.join(inputs.visible_exits)}")
    if inputs.same_room_entities:
        trimmed = list(inputs.same_room_entities)[:12]
        lines.append(f"  same_room: {', '.join(trimmed)}")

    lines.append("Runtime:")
    if inputs.installed_worlds:
        worlds = ", ".join(f"{wid}({root})" for wid, root in inputs.installed_worlds)
        lines.append(f"  installed_worlds: {worlds}")
    else:
        lines.append("  installed_worlds: (none besides Singularity Room)")
    lines.append(f"  tools_available: {inputs.tool_surface_count}")

    if inputs.recent_commands:
        lines.append("Session recent commands (oldest->newest):")
        for cmd, result in list(inputs.recent_commands)[-5:]:
            top = (result or "").splitlines()[0] if result else ""
            if len(top) > 160:
                top = top[:157] + "..."
            lines.append(f"  - {cmd} -> {top}")
    return "\n".join(lines)


def build_world_snapshot_from_session(
    session,
    *,
    caller_username: Optional[str],
    caller_roles: Sequence[str] = (),
    caller_location_node_id: Optional[int] = None,
    agent_node_attrs: Optional[Dict[str, Any]] = None,
    tool_surface_count: int = 0,
    recent_commands: Sequence[Tuple[str, str]] = (),
) -> str:
    from app.models.graph import Node

    caller_location_name: Optional[str] = None
    caller_location_short_desc: Optional[str] = None
    visible_exits: List[str] = []
    same_room_entities: List[str] = []
    if caller_location_node_id and session is not None:
        try:
            room = session.query(Node).filter(Node.id == caller_location_node_id).first()
            if room is not None:
                caller_location_name = room.name or None
                caller_location_short_desc = (room.description or "").splitlines()[0][:140] or None
                siblings = (
                    session.query(Node)
                    .filter(
                        Node.location_id == caller_location_node_id,
                        Node.is_active == True,  # noqa: E712
                    )
                    .limit(12)
                    .all()
                )
                for n in siblings:
                    same_room_entities.append(f"{n.type_code}:{n.name or n.id}")
        except Exception:
            pass

    active_world: Optional[str] = None
    world_location: Optional[str] = None
    if agent_node_attrs:
        active_world = str(agent_node_attrs.get("active_world") or "") or None
        world_location = str(agent_node_attrs.get("world_location") or "") or None

    installed_worlds = installed_worlds_from_session(session)

    return build_world_snapshot(
        WorldSnapshotInputs(
            caller_username=caller_username,
            caller_roles=caller_roles,
            caller_location_name=caller_location_name,
            caller_location_short_desc=caller_location_short_desc,
            caller_active_world=active_world,
            caller_world_location=world_location,
            visible_exits=visible_exits,
            same_room_entities=same_room_entities,
            installed_worlds=installed_worlds,
            tool_surface_count=tool_surface_count,
            recent_commands=recent_commands,
        )
    )


def _llm_hint_from_command_node(session, name: str) -> Optional[str]:
    if session is None:
        return None
    try:
        from app.models.graph import Node

        row = (
            session.query(Node)
            .filter(
                Node.type_code == "system_command_ability",
                Node.attributes["command_name"].astext == name,
                Node.is_active == True,  # noqa: E712
            )
            .first()
        )
        if row is None:
            return None
        hint = (row.attributes or {}).get("llm_hint")
        if isinstance(hint, str) and hint.strip():
            return hint.strip()
    except Exception:
        return None
    return None


def build_llm_tool_manifest(
    surface,
    command_registry,
    *,
    session=None,
    max_description_chars: int = 240,
    include_json_example: bool = True,
) -> Tuple[str, List[ToolSchema]]:
    schemas = tool_schemas_from_surface(surface, command_registry)

    patched: List[ToolSchema] = []
    text_rows: List[str] = []
    for schema in schemas:
        hint = _llm_hint_from_command_node(session, schema.name)
        desc = (hint or schema.description or "").strip()
        if len(desc) > max_description_chars:
            desc = desc[: max_description_chars - 3] + "..."
        patched.append(ToolSchema(name=schema.name, description=desc, input_schema=dict(schema.input_schema)))
        cmd = command_registry.get_command(schema.name)
        usage = ""
        if cmd is not None:
            try:
                usage = (cmd.get_usage() or "").strip()
            except Exception:
                usage = ""
        row = f"- {schema.name}: {desc}"
        if usage:
            row += f"  (usage: {usage})"
        if include_json_example:
            row += f"  example: {json.dumps({'commands': [{'name': schema.name, 'args': []}]}, ensure_ascii=False)}"
        text_rows.append(row)

    text = "\n".join(text_rows)
    return text, patched
