"""Context assembly for AICO (and sibling npc_agent) LLM ticks.

Three public builders:

* :func:`build_ontology_primer` — renders the maintainer-reviewed system
  primer markdown (``docs/models/SPEC/AICO_SYSTEM_PRIMER.md``) with runtime
  placeholder substitution. Optionally slices by section key. Loaded once
  per process and cached; the file is also surfaced to humans via the
  ``primer`` command.
* :func:`build_world_snapshot` — per-tick dynamic facts (caller identity,
  current location, installed worlds, recent commands) to inject into the
  first Plan user turn.
* :func:`build_llm_tool_manifest` — dual-form tool manifest: plain text for
  JSON fallback channels and a list of :class:`ToolSchema` for native
  ``tool_use`` channels.

None of these functions touch provider wire formats; the framework picks
which representation to hand to the LLM client based on
``LlmClient.supports_tools()``.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from app.game_engine.agent_runtime.tool_calling import ToolSchema, tool_schemas_from_surface


# Section key -> markdown heading fragment (without the "## " prefix).
PRIMER_SECTIONS: Tuple[Tuple[str, str], ...] = (
    ("identity", "1. Identity"),
    ("structure", "2. Structure"),
    ("ontology", "3. Ontology"),
    ("world", "4. World"),
    ("actions", "5. Actions"),
    ("interaction", "6. Interaction"),
    ("memory", "7. Memory"),
    ("invariants", "8. Invariants"),
    ("examples", "9. Examples"),
)

_SECTION_KEYS = {key for key, _ in PRIMER_SECTIONS}


# ---------------------------- primer loading ----------------------------


def _primer_default_path() -> Path:
    """Resolve the SSOT markdown file relative to this package.

    The docs directory sits next to ``backend`` at the workspace root:

    ``backend/app/game_engine/agent_runtime/aico_world_context.py`` →
    ``parents[4] == <workspace_root>`` (contains both ``backend/`` and ``docs/``).
    """
    here = Path(__file__).resolve()
    workspace_root = here.parents[4]
    return workspace_root / "docs" / "models" / "SPEC" / "AICO_SYSTEM_PRIMER.md"


_primer_cache_lock = threading.Lock()
_primer_raw_cache: Optional[str] = None
_primer_sections_cache: Optional[Dict[str, str]] = None


def _load_primer_raw(path: Optional[Path] = None) -> str:
    """Read and cache the SSOT markdown. Subsequent calls reuse the cache."""
    global _primer_raw_cache, _primer_sections_cache
    with _primer_cache_lock:
        if _primer_raw_cache is None or path is not None:
            p = path if path is not None else _primer_default_path()
            if not p.exists():
                raise FileNotFoundError(f"AICO system primer not found at: {p}")
            _primer_raw_cache = p.read_text(encoding="utf-8")
            _primer_sections_cache = _slice_primer_sections(_primer_raw_cache)
        return _primer_raw_cache


def _slice_primer_sections(raw: str) -> Dict[str, str]:
    """Split the primer into ``{section_key: markdown_body}``.

    The section body excludes the ``## N. Title`` heading and the trailing
    ``---`` or EOF delimiter, so each slice can be rendered alone.
    """
    out: Dict[str, str] = {}
    lines = raw.splitlines()
    markers: List[Tuple[int, str]] = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        for key, title in PRIMER_SECTIONS:
            if stripped == f"## {title}":
                markers.append((idx, key))
                break
    for i, (start, key) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(lines)
        body_lines = lines[start + 1 : end]
        # Trim leading/trailing blank lines.
        while body_lines and not body_lines[0].strip():
            body_lines.pop(0)
        while body_lines and not body_lines[-1].strip():
            body_lines.pop()
        out[key] = "\n".join(body_lines)
    return out


def primer_toc() -> List[Tuple[str, str]]:
    """Public accessor for section (key, title) pairs in order."""
    return list(PRIMER_SECTIONS)


def _substitute_placeholders(text: str, values: Dict[str, str]) -> str:
    out = text
    for k, v in values.items():
        out = out.replace("{" + k + "}", v)
    return out


def _resolve_primer_placeholders(
    *,
    for_agent: Optional[str],
    caller_location_name: Optional[str],
    primary_world_root: Optional[str],
) -> Dict[str, str]:
    return {
        "AICO_SERVICE_ID": for_agent or "aico",
        "AICO_LOCATION": caller_location_name or "Singularity Room",
        "PRIMARY_WORLD_ROOT": primary_world_root or "Singularity Room",
    }


def build_ontology_primer(
    section: Optional[str] = None,
    *,
    for_agent: Optional[str] = None,
    raw: bool = False,
    caller_location_name: Optional[str] = None,
    primary_world_root: Optional[str] = None,
    primer_path: Optional[Path] = None,
) -> str:
    """Return the primer text (optionally section-sliced).

    ``section`` — one of the keys from :data:`PRIMER_SECTIONS`; when
    ``None`` returns the whole document (minus the leading ``> Role of
    this document`` banner, which is maintainer-facing).

    ``raw`` — return the markdown with placeholders intact; used by the
    ``primer --raw`` maintainer branch.

    ``for_agent`` — which `service_id` the primer is being rendered for.
    Substitutes ``{AICO_SERVICE_ID}``; defaults to ``"aico"``.
    """
    _load_primer_raw(primer_path)
    raw_text = _primer_raw_cache or ""
    if raw:
        chosen = raw_text
    else:
        body = _strip_maintainer_banner(raw_text)
        if section is None or section == "":
            chosen = body
        else:
            key = section.strip().lower()
            if key not in _SECTION_KEYS:
                raise ValueError(
                    f"unknown primer section '{section}'; known: {sorted(_SECTION_KEYS)}"
                )
            assert _primer_sections_cache is not None  # loaded above
            chosen = _primer_sections_cache.get(key, "")

    if raw:
        return chosen.rstrip() + "\n"
    placeholders = _resolve_primer_placeholders(
        for_agent=for_agent,
        caller_location_name=caller_location_name,
        primary_world_root=primary_world_root,
    )
    return _substitute_placeholders(chosen, placeholders).rstrip() + "\n"


def _strip_maintainer_banner(text: str) -> str:
    """Remove the leading ``> Role of this document`` block and first ``---``.

    The banner is for maintainers reading the SPEC and should not be shown
    to the LLM or to users consulting ``primer`` — everything the runtime
    needs starts at ``## 1. Identity``.
    """
    lines = text.splitlines()
    # Find the first heading line.
    for idx, line in enumerate(lines):
        if line.strip().startswith("## 1. Identity"):
            return "\n".join(lines[idx:])
    return text


def identity_and_invariants_snippet(
    *,
    for_agent: Optional[str] = None,
    caller_location_name: Optional[str] = None,
    primary_world_root: Optional[str] = None,
) -> str:
    """Return just Identity + Invariants — the Tier-1 static system segment.

    Used by the framework plumbing layer to keep the system prompt under
    ~300 tokens. Full primer stays available on demand via the ``primer``
    command.
    """
    parts: List[str] = []
    for key in ("identity", "invariants"):
        chunk = build_ontology_primer(
            section=key,
            for_agent=for_agent,
            caller_location_name=caller_location_name,
            primary_world_root=primary_world_root,
        ).rstrip()
        if chunk:
            parts.append(f"## {_title_for(key)}\n\n{chunk}")
    return "\n\n".join(parts)


def _title_for(key: str) -> str:
    for k, title in PRIMER_SECTIONS:
        if k == key:
            return title
    return key


def primer_cache_clear() -> None:
    """Drop the in-process primer cache (used by tests and primer edits)."""
    global _primer_raw_cache, _primer_sections_cache
    with _primer_cache_lock:
        _primer_raw_cache = None
        _primer_sections_cache = None


# ---------------------------- world snapshot ----------------------------


@dataclass
class WorldSnapshotInputs:
    """Explicit inputs for :func:`build_world_snapshot`.

    Kept as a dataclass (not positional args) so callers can add fields
    without breaking signatures across the codebase.
    """

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
    """Render the per-tick dynamic context block.

    Output is a compact, human-readable text block (not JSON). The LLM
    treats it as authoritative for the current tick only.
    """
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
    """Thin convenience wrapper that pulls room + installed worlds from DB.

    DB access is kept shallow and best-effort: any failure results in the
    field being elided, not the snapshot aborting.
    """
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
                # Same-room entities (characters / npc_agents / items) — cap 12
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

    installed_worlds: List[Tuple[str, str]] = []
    if session is not None:
        try:
            # world_entrance nodes live in the root room and describe installed worlds.
            rows = (
                session.query(Node)
                .filter(
                    Node.type_code == "world_entrance",
                    Node.is_active == True,  # noqa: E712
                )
                .limit(32)
                .all()
            )
            for n in rows:
                attrs = n.attributes or {}
                wid = str(attrs.get("world_id") or n.name or "").strip()
                if not wid:
                    continue
                root_name = str(attrs.get("target_display_name") or n.name or wid)
                installed_worlds.append((wid, root_name))
        except Exception:
            pass

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


# ---------------------------- tool manifest ----------------------------


def _llm_hint_from_command_node(session, name: str) -> Optional[str]:
    """Look up ``attributes.llm_hint`` on the command's ability node.

    Best-effort DB read; returns ``None`` when unavailable.
    """
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
    """Dual-form manifest: (text, schemas).

    The text form is embedded in the Plan user turn for JSON-only channels.
    The schema form is passed to ``complete_with_tools`` on clients that
    support native tool use.

    Description precedence: ``attributes.llm_hint`` (per-command graph node)
    → ``BaseCommand.description`` → ``BaseCommand.get_help()``.
    """
    schemas = tool_schemas_from_surface(surface, command_registry)

    # Patch schema descriptions with llm_hint when present.
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


# Small registry-based cache key — callers may invalidate via primer_cache_clear
# when the primer source file is edited at runtime (dev loop).
_primer_mtime_cache: Dict[str, float] = {}


def primer_reload_if_stale(path: Optional[Path] = None) -> bool:
    """Reload primer file if mtime changed since last load.

    Returns True when reloaded. Safe to call per-tick in dev; no-op when
    the file is unchanged.
    """
    p = path if path is not None else _primer_default_path()
    if not p.exists():
        return False
    mtime = p.stat().st_mtime
    last = _primer_mtime_cache.get(str(p))
    if last is not None and mtime <= last:
        return False
    _primer_mtime_cache[str(p)] = mtime
    primer_cache_clear()
    _load_primer_raw(p)
    return True


# Keep a single exported callable for the primer command to use without
# exposing the module's internals.
primer_path_for_display: Callable[[], Path] = _primer_default_path
