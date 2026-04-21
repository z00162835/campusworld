"""``find`` and ``describe`` — read-only graph discovery commands.

Both commands are first-class tools for AICO (and other npc_agents) so the
LLM can ground its answers in actual graph state rather than guessing.
They are also usable by humans: typical SSH sessions benefit from a quick
inspect while navigating CampusWorld.

Naming and semantics follow Evennia's admin ``@find`` / ``examine``
conventions while adapting to CampusWorld's graph-native ontology:

* ``find <query>`` — ILIKE on ``Node.name`` + ``Node.description`` (default).
* ``find #<id>`` — direct id lookup (Evennia ``#dbref`` parity).
* ``find *<account>`` — convenience shorthand for ``--type account``.
* ``--exact`` / ``--startswith`` — tighten the name match.
* ``--in <room_id>`` — restrict to nodes with that ``location_id``.
* ``--type <type_code>`` / ``--limit <N>`` — standard filters.

Neither command mutates state; both respect the caller's authorization via
the normal ``command_policies`` path. Output is bounded to keep LLM context
cost small (max 50 results for ``find``; per-node attribute/edge preview
for ``describe``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.commands.base import CommandContext, CommandResult, SystemCommand


_DEFAULT_LIMIT = 12
_MAX_LIMIT = 50
_DESC_PREVIEW_CHARS = 240


def _find_cfg():
    """Return the live ``commands.find`` settings block.

    Re-reads on every call so tests can monkeypatch this helper to inject a
    bespoke ``FindCommandConfig`` without touching global state. Falls back to
    defaults when the config manager is not initialised (e.g. pure unit tests
    that never load ``settings.yaml``).
    """
    try:
        from app.core.config_manager import config_manager
        from app.core.settings import create_settings_from_config

        return create_settings_from_config(config_manager).commands.find
    except Exception:
        from app.core.settings import FindCommandConfig

        return FindCommandConfig()


class _ParsedFindArgs:
    __slots__ = (
        "query",
        "node_id",
        "account_name",
        "type_code",
        "exact",
        "startswith",
        "in_location",
        "limit",
        "name",
        "describe",
        "all",
        "error",
    )

    def __init__(self):
        self.query: Optional[str] = None
        self.node_id: Optional[int] = None
        self.account_name: Optional[str] = None
        self.type_code: Optional[str] = None
        self.exact: bool = False
        self.startswith: bool = False
        self.in_location: Optional[int] = None
        self.limit: int = _DEFAULT_LIMIT
        self.name: Optional[str] = None
        self.describe: Optional[str] = None
        self.all: bool = False
        self.error: Optional[str] = None


# --------------------- flag-spec dispatch table (v3) ----------------------
#
# The parser is table-driven: each canonical long flag is described once in
# ``_FLAG_SPEC`` as a ``_FlagSpec`` row, and short aliases in ``_FLAG_ALIASES``
# resolve to the canonical long form. Adding a future flag is a one-row edit
# here; ``_parse_find_args`` itself never grows new branches.


def _coerce_type(v: str) -> Optional[str]:
    return v.strip() or None


def _coerce_limit(v: str) -> int:
    return max(1, min(_MAX_LIMIT, int(v)))


def _coerce_loc(v: str) -> int:
    return int(v)


@dataclass(frozen=True)
class _FlagSpec:
    """Declarative description of one CLI flag.

    ``kind`` is one of:
      - ``"value"``  consumes the next argv token; stored via ``dest`` after
                     ``coerce``; ``ValueError`` maps to a parser error using
                     ``bad_value_msg`` (falls back to ``need_value_msg``).
      - ``"bool"``   sets ``dest`` to ``True``; no value consumed.
      - ``"error"``  short-circuits parsing with ``error_msg`` (used for
                     migration traps such as the removed ``--location``).
    """

    kind: str
    dest: Optional[str] = None
    coerce: Optional[Callable[[str], Any]] = None
    need_value_msg: str = ""
    bad_value_msg: str = ""
    error_msg: str = ""


_FLAG_SPEC: Dict[str, _FlagSpec] = {
    "--type": _FlagSpec(
        "value",
        dest="type_code",
        coerce=_coerce_type,
        need_value_msg="--type requires a value (e.g. room, account, world_entrance)",
    ),
    "--limit": _FlagSpec(
        "value",
        dest="limit",
        coerce=_coerce_limit,
        need_value_msg="--limit requires a number",
        bad_value_msg="--limit must be an integer",
    ),
    "--in": _FlagSpec(
        "value",
        dest="in_location",
        coerce=_coerce_loc,
        need_value_msg="--in requires a room id",
        bad_value_msg="--in must be an integer room id",
    ),
    "--name": _FlagSpec(
        "value",
        dest="name",
        coerce=str,
        need_value_msg="--name requires a value",
    ),
    "--describe": _FlagSpec(
        "value",
        dest="describe",
        coerce=str,
        need_value_msg="--describe requires a value",
    ),
    "--exact": _FlagSpec("bool", dest="exact"),
    "--startswith": _FlagSpec("bool", dest="startswith"),
    "--all": _FlagSpec("bool", dest="all"),
    # v2 -> v3 migration trap.
    "--location": _FlagSpec(
        "error",
        error_msg="--location has been renamed in v3; use --in <room_id> or -loc <room_id>",
    ),
}

_FLAG_ALIASES: Dict[str, str] = {
    "-t": "--type",
    "-l": "--limit",
    "-loc": "--in",
    "-n": "--name",
    "-des": "--describe",
    "-a": "--all",
}


def _resolve_flag(token: str) -> Optional[Tuple[str, _FlagSpec]]:
    """Return ``(canonical, spec)`` for a flag token, or ``None`` if unknown."""
    canonical = _FLAG_ALIASES.get(token, token)
    spec = _FLAG_SPEC.get(canonical)
    return (canonical, spec) if spec is not None else None


def _parse_find_args(args: List[str]) -> _ParsedFindArgs:
    """Parse ``find`` arguments (v3; see docs/commands/SPEC/features/F01_FIND_COMMAND.md).

    Accepts Evennia-style positional shortcuts (``#id``, ``*account``) plus
    the v3 flag surface. The first non-flag token is treated as the
    positional query; additional positional tokens are joined with spaces so
    callers may write ``find hi campus`` without quoting. Flags are
    dispatched through ``_FLAG_SPEC`` / ``_FLAG_ALIASES``, so adding a new
    flag is a one-row change at the table.
    """
    out = _ParsedFindArgs()
    positional: List[str] = []
    i = 0
    while i < len(args):
        token = args[i]
        resolved = _resolve_flag(token)
        if resolved is not None:
            canonical, spec = resolved
            if spec.kind == "error":
                out.error = spec.error_msg
                return out
            if spec.kind == "bool":
                setattr(out, spec.dest, True)
                i += 1
                continue
            # value flag
            if i + 1 >= len(args):
                out.error = spec.need_value_msg
                return out
            raw = args[i + 1]
            try:
                setattr(out, spec.dest, spec.coerce(raw))
            except ValueError:
                prefix = spec.bad_value_msg or spec.need_value_msg
                out.error = f"{prefix}, got {raw!r}"
                return out
            i += 2
            continue
        # Unknown token — anything starting with '-' (but not a negative
        # number) is treated as a typo rather than positional.
        if token.startswith("--") or (
            token.startswith("-") and len(token) > 1 and not token[1].isdigit()
        ):
            out.error = f"unknown flag: {token}"
            return out
        positional.append(token)
        i += 1

    # --- cross-flag validation ---
    if out.exact and out.startswith:
        out.error = "--exact and --startswith are mutually exclusive"
        return out
    if positional and (out.name is not None or out.describe is not None):
        out.error = (
            "positional query and --name/--describe are mutually exclusive; "
            "pick one form"
        )
        return out

    # --- positional interpretation ---
    if positional:
        first = positional[0]
        if first.startswith("#") and len(first) > 1 and all(
            ch.isdigit() for ch in first[1:]
        ):
            out.node_id = int(first[1:])
            if len(positional) > 1:
                out.error = "unexpected extra arguments after #<id> lookup"
                return out
        elif first.startswith("*") and len(first) > 1:
            account = " ".join([first[1:], *positional[1:]]).strip()
            if not account:
                out.error = "*<account> requires an account name"
                return out
            out.account_name = account
            # Narrow type to account unless the caller overrides.
            if out.type_code is None:
                out.type_code = "account"
        else:
            out.query = " ".join(positional).strip() or None

    has_any_predicate = any(
        v is not None
        for v in (
            out.query,
            out.node_id,
            out.account_name,
            out.name,
            out.describe,
            out.type_code,
            out.in_location,
        )
    )
    if not has_any_predicate:
        out.error = "find requires a query, #<id>, *<account>, -n, -des, --type, or --in"
    return out


def _truncate(text: Optional[str], max_chars: int) -> str:
    s = (text or "").strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1].rstrip() + "…"


class FindCommand(SystemCommand):
    """Find graph nodes by name/description/id/account (Evennia-style ``find``)."""

    def __init__(self):
        super().__init__(
            "find",
            (
                "Find graph nodes via ILIKE on name/description, `#<id>` for "
                "direct lookup, `*<account>` for account. Returns "
                "`data.results` [{id, type_code, name, location_id, "
                "description}] + `data.total`/`data.next_offset`. "
                "Not semantic search."
            ),
            aliases=["@find", "locate"],
        )

    def get_usage(self) -> str:
        return (
            "find <query | #<id> | *<account>> "
            "[--type <type_code>] [--exact] [--startswith] "
            "[--in <room_id>] [--limit <N>]"
        )

    def _get_specific_help(self) -> str:
        return (
            "\nSearches Node.name and Node.description (case-insensitive)."
            "\nShortcuts: `#<id>` for direct id lookup, `*<account>` for account-name lookup."
            "\nCommon type_codes: account, character, room, world, world_entrance,"
            "\n                   building, item, system_command_ability, npc_agent"
            "\n\nExamples:"
            "\n  find hicampus --type world_entrance"
            "\n  find 广场 --limit 5"
            "\n  find --type room --in 1"
            "\n  find #42"
            "\n  find *admin"
            "\n  find atrium --exact"
        )

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        session = getattr(context, "db_session", None)
        if session is None:
            return CommandResult.error_result("find requires an active DB session")

        parsed = _parse_find_args(args)
        if parsed.error:
            return CommandResult.error_result(parsed.error)

        # Direct id lookup — Evennia `find #42` parity.
        if parsed.node_id is not None:
            row = _lookup_by_id(session, parsed.node_id)
            if row is None:
                return CommandResult.success_result(
                    f"No active node for id={parsed.node_id}.",
                    data=_empty_find_payload(parsed),
                )
            return _render_find_results([row], total=1, parsed=parsed)

        rows, total = _run_find_query(session, parsed=parsed)
        if not rows:
            hint = _describe_no_match(parsed)
            return CommandResult.success_result(hint, data=_empty_find_payload(parsed))
        return _render_find_results(rows, total=total, parsed=parsed)


class DescribeCommand(SystemCommand):
    """Render one graph node with its attributes, location, and a sample of edges."""

    def __init__(self):
        super().__init__(
            "describe",
            "Show a single graph node's details (type, name, description, attrs, edges).",
            aliases=["examine", "ex"],
        )

    def get_usage(self) -> str:
        return "describe <node_id | #<id> | node_name>"

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        session = getattr(context, "db_session", None)
        if session is None:
            return CommandResult.error_result("describe requires an active DB session")
        if not args:
            return CommandResult.error_result(self.get_usage())

        raw = args[0].strip()
        if raw.startswith("#"):
            raw = raw[1:]
        node = _resolve_node_by_id_or_name(session, raw)
        if node is None:
            return CommandResult.error_result(
                f"no active node found for identifier {args[0]!r}"
            )

        lines: List[str] = []
        lines.append(f"[{node.id}] {node.type_code}: {node.name}")
        if node.description:
            lines.append("")
            lines.append(node.description.strip())
        if node.location_id:
            lines.append("")
            lines.append(f"location_id: {node.location_id}")
        if node.home_id:
            lines.append(f"home_id: {node.home_id}")
        attrs = node.attributes or {}
        if isinstance(attrs, dict) and attrs:
            preview_keys = sorted(attrs.keys())[:12]
            lines.append("")
            lines.append("attributes (preview):")
            for k in preview_keys:
                v = attrs[k]
                vs = str(v)
                if len(vs) > 160:
                    vs = vs[:157] + "..."
                lines.append(f"  {k}: {vs}")
            if len(attrs) > len(preview_keys):
                lines.append(f"  ... (+{len(attrs) - len(preview_keys)} more)")

        out_edges = _sample_out_edges(session, node.id, limit=8)
        if out_edges:
            lines.append("")
            lines.append("out-edges (sample):")
            for rel, other in out_edges:
                other_label = (
                    f"[{other.id}] {other.type_code}: {other.name}"
                    if other is not None
                    else f"(target #{rel.target_id} missing)"
                )
                role = f" role={rel.target_role}" if rel.target_role else ""
                lines.append(f"  -[{rel.type_code}{role}]-> {other_label}")

        return CommandResult.success_result(
            "\n".join(lines),
            data={
                "id": node.id,
                "type_code": node.type_code,
                "name": node.name,
                "location_id": node.location_id,
            },
        )


# -------------------- query helpers --------------------


# Pagination: ``find`` currently exposes a single page bounded by
# ``parsed.limit`` (hard-capped at ``_MAX_LIMIT``). ``data.total`` is the
# full match count, so callers/agents can tell when truncation happened.
# ``data.next_offset`` is reserved for a future ``--offset`` switch; today
# it is ``None`` when there is nothing more to fetch, and equal to
# ``len(results)`` when ``total > len(results)``. Keep this field stable
# so LLM manifests can promise an iteration contract.


def _find_query_descriptor(parsed: _ParsedFindArgs) -> dict:
    """Serialize the parsed query into a stable ``data.query`` payload."""

    return {
        "text": parsed.query,
        "account": parsed.account_name,
        "node_id": parsed.node_id,
        "type_code": parsed.type_code,
        "in_location": parsed.in_location,
        "exact": parsed.exact,
        "startswith": parsed.startswith,
        "limit": parsed.limit,
    }


def _empty_find_payload(parsed: _ParsedFindArgs) -> dict:
    return {
        "results": [],
        "total": 0,
        "next_offset": None,
        "query": _find_query_descriptor(parsed),
    }


def _describe_no_match(parsed: _ParsedFindArgs) -> str:
    parts: List[str] = []
    if parsed.query:
        parts.append(f"query={parsed.query!r}")
    if parsed.account_name:
        parts.append(f"account={parsed.account_name!r}")
    if parsed.type_code:
        parts.append(f"type={parsed.type_code!r}")
    if parsed.in_location is not None:
        parts.append(f"in_location={parsed.in_location}")
    if parsed.exact:
        parts.append("exact=True")
    if parsed.startswith:
        parts.append("startswith=True")
    return "No active nodes matched " + ", ".join(parts) + "." if parts else (
        "No active nodes matched."
    )


def _render_find_results(
    rows: List[Any], *, total: int, parsed: _ParsedFindArgs
) -> CommandResult:
    lines: List[str] = []
    descriptor: List[str] = []
    if parsed.query:
        descriptor.append(f"query={parsed.query!r}")
    if parsed.account_name:
        descriptor.append(f"account={parsed.account_name!r}")
    if parsed.node_id is not None:
        descriptor.append(f"id={parsed.node_id}")
    if parsed.type_code:
        descriptor.append(f"type={parsed.type_code!r}")
    if parsed.in_location is not None:
        descriptor.append(f"in_location={parsed.in_location}")

    header = (
        f"Found {len(rows)} node(s)"
        + (f" (of {total} matching, truncated)" if total > len(rows) else "")
        + (" for " + " ".join(descriptor) if descriptor else "")
        + ":"
    )
    lines.append(header)
    result_data: List[dict] = []
    for n in rows:
        brief = _truncate(n.description, _DESC_PREVIEW_CHARS)
        loc_part = f" loc={n.location_id}" if n.location_id else ""
        lines.append(
            f"  [{n.id}] {n.type_code}: {n.name}{loc_part}"
            + (f"\n      {brief}" if brief else "")
        )
        result_data.append(
            {
                "id": n.id,
                "type_code": n.type_code,
                "name": n.name,
                "location_id": n.location_id,
                "description": brief,
            }
        )
    lines.append("")
    lines.append("Hint: run `describe <id>` for full details.")
    next_offset = len(result_data) if total > len(result_data) else None
    return CommandResult.success_result(
        "\n".join(lines),
        data={
            "results": result_data,
            "total": total,
            "next_offset": next_offset,
            "query": _find_query_descriptor(parsed),
        },
    )


def _lookup_by_id(session, node_id: int):
    from app.models.graph import Node

    return (
        session.query(Node)
        .filter(Node.id == node_id, Node.is_active == True)  # noqa: E712
        .first()
    )


def _run_find_query(session, *, parsed: _ParsedFindArgs) -> Tuple[List[Any], int]:
    """Return ``(rows, total_matching)`` with ``len(rows) <= parsed.limit``.

    Matches ``Node.name`` / ``Node.description`` with the name-pattern
    strictness derived from ``--exact`` / ``--startswith``. Inactive nodes
    and nodes outside ``--in`` (if given) are excluded.
    """
    from sqlalchemy import or_

    from app.models.graph import Node

    q = session.query(Node).filter(Node.is_active == True)  # noqa: E712

    if parsed.type_code:
        q = q.filter(Node.type_code == parsed.type_code.strip())
    if parsed.in_location is not None:
        q = q.filter(Node.location_id == parsed.in_location)

    search_term = parsed.query or parsed.account_name
    if search_term:
        if parsed.exact:
            q = q.filter(Node.name.ilike(search_term))
        elif parsed.startswith:
            q = q.filter(Node.name.ilike(f"{search_term}%"))
        else:
            like = f"%{search_term}%"
            q = q.filter(or_(Node.name.ilike(like), Node.description.ilike(like)))

    total = q.count()
    rows = q.order_by(Node.type_code.asc(), Node.name.asc()).limit(parsed.limit).all()
    return rows, total


def _resolve_node_by_id_or_name(session, raw: str):
    """Try integer id first; fall back to active-node name match."""
    from app.models.graph import Node

    try:
        nid = int(raw)
        row = session.query(Node).filter(Node.id == nid).first()
        if row is not None:
            return row
    except ValueError:
        pass
    return (
        session.query(Node)
        .filter(Node.name == raw, Node.is_active == True)  # noqa: E712
        .first()
    )


def _sample_out_edges(session, node_id: int, *, limit: int = 8):
    """Return up to ``limit`` outgoing relationships with the target node.

    Best-effort: any DB error yields an empty list so ``describe`` keeps
    working even with partial data.
    """
    from app.models.graph import Node, Relationship

    try:
        rels = (
            session.query(Relationship)
            .filter(Relationship.source_id == node_id, Relationship.is_active == True)  # noqa: E712
            .order_by(Relationship.type_code.asc(), Relationship.id.asc())
            .limit(limit)
            .all()
        )
        out: List[Tuple[Any, Any]] = []
        for r in rels:
            other = session.query(Node).filter(Node.id == r.target_id).first()
            out.append((r, other))
        return out
    except Exception:
        return []


# Module-level list mirrors the SYSTEM_COMMANDS pattern used by init_commands.
GRAPH_INSPECT_COMMANDS: List[SystemCommand] = [FindCommand(), DescribeCommand()]
