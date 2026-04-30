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

from app.commands.tool_semantics import get_command_tool_semantics, pick_routing_hint
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


def _llm_hint_from_command_node(session, name: str, *, locale: str) -> Optional[str]:
    if session is None:
        return None
    try:
        from app.commands.i18n.locale_text import FALLBACK_CHAIN, pick_i18n
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
        attrs = row.attributes or {}
        raw_i18n = attrs.get("llm_hint_i18n")
        if isinstance(raw_i18n, dict) and raw_i18n:
            m = {str(k): str(v) for k, v in raw_i18n.items() if v is not None}
            picked = pick_i18n(m, locale, fallbacks=FALLBACK_CHAIN, legacy_default=None).value
            if picked:
                return picked
        hint = attrs.get("llm_hint")
        if isinstance(hint, str) and hint.strip():
            return hint.strip()
    except Exception:
        return None
    return None


def _command_semantics_from_node(session, name: str) -> Dict[str, Any]:
    base = get_command_tool_semantics(name)
    if session is None:
        return base
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
            return base
        attrs = row.attributes or {}
        profile = str(attrs.get("interaction_profile") or "").strip().lower()
        if profile in {"document", "read", "mutate"}:
            base["interaction_profile"] = profile
        if isinstance(attrs.get("invocation_guard"), dict):
            base["invocation_guard"] = dict(attrs["invocation_guard"])
        routing = pick_routing_hint(attrs, "en-US")
        if routing:
            base["routing_hint"] = routing
        if isinstance(attrs.get("routing_hint_i18n"), dict):
            base["routing_hint_i18n"] = dict(attrs["routing_hint_i18n"])
    except Exception:
        return base
    return base


def _manifest_section_title(locale: str, profile: str) -> str:
    zh = str(locale or "").lower().startswith("zh")
    if profile == "document":
        return "文档类（document）" if zh else "Document tools"
    if profile == "read":
        return "查询类（read）" if zh else "Read-only tools"
    if profile == "mutate":
        return "变更类（mutate）" if zh else "State-changing tools"
    return "其它" if zh else "Other tools"


def build_llm_tool_manifest(
    surface,
    command_registry,
    *,
    session=None,
    locale: Optional[str] = None,
    max_description_chars: int = 240,
    include_json_example: bool = True,
) -> Tuple[str, List[ToolSchema]]:
    from app.commands.i18n.locale_text import tool_manifest_locale

    loc = tool_manifest_locale(locale)
    schemas = tool_schemas_from_surface(surface, command_registry)

    patched: List[ToolSchema] = []
    rows_by_profile: Dict[str, List[str]] = {"document": [], "read": [], "mutate": [], "other": []}
    for schema in schemas:
        hint = _llm_hint_from_command_node(session, schema.name, locale=loc)
        sem = _command_semantics_from_node(session, schema.name)
        cmd = command_registry.get_command(schema.name)
        reg_desc = ""
        if cmd is not None:
            try:
                reg_desc = (cmd.get_localized_description(loc) or "").strip()
            except Exception:
                reg_desc = (getattr(cmd, "description", None) or "").strip()
        desc = (hint or reg_desc or schema.description or "").strip()
        profile = str(sem.get("interaction_profile") or "read").strip().lower()
        if profile not in {"document", "read", "mutate"}:
            profile = "other"

        attrs_for_hint = {
            "routing_hint": sem.get("routing_hint"),
            "routing_hint_i18n": sem.get("routing_hint_i18n"),
        }
        routing_hint = pick_routing_hint(attrs_for_hint, loc) or ""
        schema_desc = desc
        if routing_hint:
            schema_desc = f"{desc} Routing: {routing_hint}"
        if len(schema_desc) > max_description_chars:
            schema_desc = schema_desc[: max_description_chars - 3] + "..."
        patched.append(
            ToolSchema(name=schema.name, description=schema_desc, input_schema=dict(schema.input_schema))
        )
        usage = ""
        if cmd is not None:
            try:
                usage = (cmd.get_localized_usage(loc) or "").strip()
            except Exception:
                try:
                    usage = (cmd.get_usage() or "").strip()
                except Exception:
                    usage = ""
        row = f"- {schema.name}: {desc}"
        if routing_hint:
            row += f"  (routing: {routing_hint})"
        if usage:
            row += f"  (usage: {usage})"
        if include_json_example:
            row += f"  example: {json.dumps({'commands': [{'name': schema.name, 'args': []}]}, ensure_ascii=False)}"
        rows_by_profile[profile].append(row)

    text_rows: List[str] = []
    for profile in ("document", "read", "mutate", "other"):
        rows = rows_by_profile.get(profile) or []
        if not rows:
            continue
        text_rows.append(f"[{_manifest_section_title(loc, profile)}]")
        text_rows.extend(rows)
    text = "\n".join(text_rows)
    return text, patched
