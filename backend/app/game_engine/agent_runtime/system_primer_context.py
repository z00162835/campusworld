"""CampusWorld system primer: maintainer markdown + runtime placeholder substitution.

The ``primer`` command and any ``npc_agent`` runtime use this module — it is
not AICO-specific. Dynamic graph-backed annexes (when a DB session is
available) append after the static slices for ontology/world sections.

SSOT: ``docs/models/SPEC/CAMPUSWORLD_SYSTEM_PRIMER.md``.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from app.game_engine.agent_runtime.command_caller_graph import (
    resolve_caller_location_id,
    resolve_caller_node_id,
    resolve_room_display_name,
)
from app.game_engine.agent_runtime.world_runtime_queries import installed_worlds_from_session

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
    ("commands", "9. Commands"),
)

_SECTION_KEYS = {key for key, _ in PRIMER_SECTIONS}
_SECTION_ALIASES = {
    "examples": "commands",
}

_primer_cache_lock = threading.Lock()
_primer_raw_cache: Optional[str] = None
_primer_sections_cache: Optional[Dict[str, str]] = None
_primer_mtime_cache: Dict[str, float] = {}


def _primer_default_path() -> Path:
    here = Path(__file__).resolve()
    workspace_root = here.parents[4]
    return workspace_root / "docs" / "models" / "SPEC" / "CAMPUSWORLD_SYSTEM_PRIMER.md"


def _load_primer_raw(path: Optional[Path] = None) -> str:
    global _primer_raw_cache, _primer_sections_cache
    with _primer_cache_lock:
        if _primer_raw_cache is None or path is not None:
            p = path if path is not None else _primer_default_path()
            if not p.exists():
                raise FileNotFoundError(f"CampusWorld system primer not found at: {p}")
            _primer_raw_cache = p.read_text(encoding="utf-8")
            _primer_sections_cache = _slice_primer_sections(_primer_raw_cache)
        return _primer_raw_cache


def _slice_primer_sections(raw: str) -> Dict[str, str]:
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
        while body_lines and not body_lines[0].strip():
            body_lines.pop(0)
        while body_lines and not body_lines[-1].strip():
            body_lines.pop()
        out[key] = "\n".join(body_lines)
    return out


def primer_toc() -> List[Tuple[str, str]]:
    return list(PRIMER_SECTIONS)


def _substitute_placeholders(text: str, values: Dict[str, str]) -> str:
    out = text
    for k, v in values.items():
        out = out.replace("{" + k + "}", v)
    return out


def _neutral_primer_values(
    *,
    for_agent: Optional[str],
    caller_location_name: Optional[str],
    root_room_label: Optional[str],
) -> Dict[str, str]:
    return {
        "AGENT_SERVICE_ID": for_agent or "aico",
        "CALLER_LOCATION": caller_location_name or "Singularity Room",
        "ROOT_ROOM_LABEL": root_room_label or "Singularity Room",
    }


def _all_placeholder_keys(values: Dict[str, str]) -> Dict[str, str]:
    """Also substitute legacy AICO_* / PRIMARY_WORLD_ROOT keys from the same values."""
    sid = values["AGENT_SERVICE_ID"]
    loc = values["CALLER_LOCATION"]
    root = values["ROOT_ROOM_LABEL"]
    merged = dict(values)
    merged["AICO_SERVICE_ID"] = sid
    merged["AICO_LOCATION"] = loc
    merged["PRIMARY_WORLD_ROOT"] = root
    return merged


def _resolve_runtime_placeholders(
    *,
    for_agent: Optional[str],
    caller_location_name: Optional[str],
    primary_world_root: Optional[str],
    root_room_label: Optional[str],
) -> Dict[str, str]:
    root = root_room_label if root_room_label is not None else primary_world_root
    return _neutral_primer_values(
        for_agent=for_agent,
        caller_location_name=caller_location_name,
        root_room_label=root,
    )


def _format_node_types_annex(session) -> str:
    from app.models.graph import NodeType

    lines = ["### Graph-backed facts (active node_types)", ""]
    try:
        rows = NodeType.get_active_types(session)
        rows_sorted = sorted(rows, key=lambda r: r.type_code or "")
        for r in rows_sorted[:64]:
            desc = ""
            if r.description:
                desc = str(r.description).strip().splitlines()[0][:120]
            line = f"- `{r.type_code}` — {r.type_name or r.type_code}"
            if desc:
                line += f": {desc}"
            lines.append(line)
    except Exception:
        lines.append("- (unavailable)")
    return "\n".join(lines) + "\n"


def _format_installed_worlds_annex(session) -> str:
    lines = ["### Graph-backed facts (installed worlds)", ""]
    worlds = installed_worlds_from_session(session)
    if not worlds:
        lines.append("- (none registered as `world_entrance` in graph)")
    else:
        for wid, label in worlds:
            lines.append(f"- `{wid}` — {label}")
    return "\n".join(lines) + "\n"


def build_primer_graph_annex(session, *, section_key: Optional[str]) -> str:
    """Markdown appendix from live graph. Empty string when ``session`` is ``None``."""
    if session is None:
        return ""
    if section_key is None:
        return _format_node_types_annex(session) + "\n" + _format_installed_worlds_annex(session)
    if section_key == "ontology":
        return _format_node_types_annex(session)
    if section_key == "world":
        return _format_installed_worlds_annex(session)
    return ""


def _strip_maintainer_banner(text: str) -> str:
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if line.strip().startswith("## 1. Identity"):
            return "\n".join(lines[idx:])
    return text


def merge_system_prompt_with_primer_tier1(
    base_system_prompt: str,
    *,
    for_agent: Optional[str] = None,
    caller_location_name: Optional[str] = None,
    primary_world_root: Optional[str] = None,
    root_room_label: Optional[str] = None,
    enabled: bool = True,
) -> str:
    """Prepend identity + invariants slices (Tier-1 SSOT) before YAML/system prompt body.

    When ``enabled`` is false, returns ``base_system_prompt`` unchanged.
    """
    if not enabled:
        return base_system_prompt if base_system_prompt is not None else ""
    base = (base_system_prompt or "").strip()
    snippet = identity_and_invariants_snippet(
        for_agent=for_agent,
        caller_location_name=caller_location_name,
        primary_world_root=primary_world_root,
        root_room_label=root_room_label,
    ).strip()
    if not snippet:
        return base_system_prompt if base_system_prompt is not None else ""
    if not base:
        return snippet + "\n"
    return snippet + "\n\n" + base + "\n"


def build_ontology_primer(
    section: Optional[str] = None,
    *,
    for_agent: Optional[str] = None,
    raw: bool = False,
    caller_location_name: Optional[str] = None,
    primary_world_root: Optional[str] = None,
    root_room_label: Optional[str] = None,
    primer_path: Optional[Path] = None,
    session=None,
    primer_command_context=None,
    append_graph_annex: bool = True,
) -> str:
    """Return primer text; optional ``session`` / ``primer_command_context`` enable graph annex.

    ``primary_world_root`` is accepted as a legacy alias for ``root_room_label``.
    """
    primer_reload_if_stale(primer_path)

    eff_session = session
    if eff_session is None and primer_command_context is not None:
        eff_session = getattr(primer_command_context, "db_session", None)

    eff_caller_location = caller_location_name
    if eff_caller_location is None and eff_session is not None and primer_command_context is not None:
        try:
            cid = resolve_caller_node_id(eff_session, primer_command_context)
            lid = resolve_caller_location_id(eff_session, cid)
            eff_caller_location = resolve_room_display_name(eff_session, lid)
        except Exception:
            eff_caller_location = None

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
            key = _SECTION_ALIASES.get(key, key)
            if key not in _SECTION_KEYS:
                raise ValueError(
                    f"unknown primer section '{section}'; known: {sorted(_SECTION_KEYS)}"
                )
            assert _primer_sections_cache is not None
            chosen = _primer_sections_cache.get(key, "")

    if raw:
        return chosen.rstrip() + "\n"

    neutral = _resolve_runtime_placeholders(
        for_agent=for_agent,
        caller_location_name=eff_caller_location,
        primary_world_root=primary_world_root,
        root_room_label=root_room_label,
    )
    merged = _all_placeholder_keys(neutral)
    base = _substitute_placeholders(chosen, merged).rstrip() + "\n"

    if not append_graph_annex or eff_session is None or raw:
        return base

    sk = None if section is None or section == "" else section.strip().lower()
    annex = build_primer_graph_annex(eff_session, section_key=sk)
    if not annex.strip():
        return base
    return base.rstrip() + "\n\n" + annex.rstrip() + "\n"


def identity_and_invariants_snippet(
    *,
    for_agent: Optional[str] = None,
    caller_location_name: Optional[str] = None,
    primary_world_root: Optional[str] = None,
    root_room_label: Optional[str] = None,
) -> str:
    parts: List[str] = []
    for key in ("identity", "invariants"):
        chunk = build_ontology_primer(
            section=key,
            for_agent=for_agent,
            caller_location_name=caller_location_name,
            primary_world_root=primary_world_root,
            root_room_label=root_room_label,
            append_graph_annex=False,
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
    global _primer_raw_cache, _primer_sections_cache
    with _primer_cache_lock:
        _primer_raw_cache = None
        _primer_sections_cache = None


def primer_reload_if_stale(path: Optional[Path] = None) -> bool:
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


primer_path_for_display: Callable[[], Path] = _primer_default_path
