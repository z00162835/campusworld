"""``space`` — read-only spatial node summary (four sections) for graph SPACE nodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.commands.base import CommandContext, CommandResult, SystemCommand
from app.commands.room_connects_to_query import connects_to_exits_from_room


@dataclass
class _SpaceParse:
    mode: str = "usage"  # usage | types | id
    node_id: Optional[int] = None
    error_key: Optional[str] = None
    error_tokens: Optional[Dict[str, str]] = None

    @property
    def ok(self) -> bool:
        return self.error_key is None


# Exported for unit tests
def parse_space_args(args: Sequence[str]) -> _SpaceParse:
    """Parse ``space`` flags: no mix of ``-t`` and ``-i``."""
    toks = [str(a).strip() for a in args if str(a).strip()]
    if not toks:
        return _SpaceParse(mode="usage")
    if "-t" in toks and "-i" in toks:
        return _SpaceParse(error_key="flags.bad_combo")
    saw_t = False
    i_val: Optional[str] = None
    i = 0
    while i < len(toks):
        t = toks[i]
        if t == "-t":
            saw_t = True
            i += 1
        elif t == "-i":
            if i + 1 >= len(toks):
                return _SpaceParse(error_key="error.bad_i")
            i_val = toks[i + 1]
            i += 2
        elif t.startswith("-"):
            return _SpaceParse(
                error_key="error.unknown_flag",
                error_tokens={"token": t},
            )
        else:
            return _SpaceParse(mode="usage")
    if saw_t and i_val is not None:
        return _SpaceParse(error_key="flags.bad_combo")
    if saw_t:
        return _SpaceParse(mode="types")
    if i_val is not None:
        try:
            i_int = int(str(i_val).strip())
        except (TypeError, ValueError):
            return _SpaceParse(error_key="error.bad_id")
        if i_int < 1:
            return _SpaceParse(error_key="error.bad_id")
        return _SpaceParse(mode="id", node_id=i_int)
    return _SpaceParse(mode="usage")


def _t(locale: str, key_path: str, default: str, **kwargs: Any) -> str:
    from app.commands.i18n.command_resource import get_command_i18n_text

    s = get_command_i18n_text("space", key_path, locale, default)
    if kwargs:
        try:
            return s.format(**kwargs)
        except Exception:
            return s
    return s


def _node_space_trait(session: Any, node: Any) -> bool:
    from app.models.graph import NodeType

    nt = session.query(NodeType).filter(NodeType.id == node.type_id).first()
    if not nt:
        return False
    if str(getattr(nt, "trait_class", "") or "").upper() == "SPACE":
        return True
    if str(getattr(node, "type_code", "") or "") in (
        "building",
        "building_floor",
        "room",
        "world",
    ):
        return True
    return False


def _list_space_type_codes(session: Any) -> List[str]:
    # SPEC: list from node_types with trait_class SPACE (active types); not the whitelist path.
    from app.models.graph import NodeType

    rows: List[NodeType] = list(NodeType.get_active_types(session))
    out: List[str] = []
    for r in rows:
        if str(getattr(r, "trait_class", "") or "").upper() != "SPACE":
            continue
        c = (getattr(r, "type_code", None) or "").strip()
        if c:
            out.append(c)
    out.sort(key=lambda x: (x.lower(), x))
    return out


def _rows_occupants(session: Any, space_id: int) -> List[Any]:
    from app.models.graph import Node, NodeType

    return (
        session.query(Node)
        .join(NodeType, Node.type_id == NodeType.id)
        .filter(
            Node.location_id == space_id,
            Node.is_active == True,  # noqa: E712
            (NodeType.trait_class == "AGENT") | (Node.type_code == "account"),
        )
        .order_by(Node.id)
        .all()
    )


def _rows_devices(session: Any, space_id: int) -> List[Any]:
    from app.models.graph import Node, NodeType

    return (
        session.query(Node)
        .join(NodeType, Node.type_id == NodeType.id)
        .filter(
            Node.location_id == space_id,
            Node.is_active == True,  # noqa: E712
            NodeType.trait_class == "DEVICE",
        )
        .order_by(Node.id)
        .all()
    )


def _child_space_nodes(
    session: Any, space: Any
) -> Tuple[List[Any], str, bool]:
    """Return (rows, section4_mode, used_fallback) for non-room SPACE nodes."""
    from app.models.graph import Node, NodeType

    tc = str(getattr(space, "type_code", "") or "")
    attrs = dict(getattr(space, "attributes", {}) or {})

    def _by_location(want_type: Optional[str] = None) -> List[Any]:
        q = (
            session.query(Node)
            .join(NodeType, Node.type_id == NodeType.id)
            .filter(
                Node.location_id == int(space.id),
                Node.is_active == True,  # noqa: E712
            )
        )
        if want_type:
            q = q.filter(Node.type_code == want_type)
        else:
            q = q.filter(NodeType.trait_class == "SPACE")
        return list(q.order_by(Node.id).all())

    if tc == "room":
        return [], "room_links", False

    if tc == "building":
        rows = _by_location("building_floor")
        if rows:
            return rows, "children", False
        bpkg = str(attrs.get("package_node_id") or "").strip()
        if bpkg:
            wid = str(attrs.get("world_id") or "").strip()
            hit = _nodes_by_attr_in_package(
                session,
                type_code="building_floor",
                attr_key="building_id",
                attr_value=bpkg,
                world_id=wid,
            )
            if hit:
                return hit, "fallback_attr", True
        return [], "children", False

    if tc == "building_floor":
        rows = _by_location("room")
        if rows:
            return rows, "children", False
        fpkg = str(attrs.get("package_node_id") or "").strip()
        if fpkg:
            wid = str(attrs.get("world_id") or "").strip()
            hit = _nodes_by_attr_in_package(
                session,
                type_code="room",
                attr_key="floor_id",
                attr_value=fpkg,
                world_id=wid,
            )
            if hit:
                return hit, "fallback_attr", True
        return [], "children", False

    rows = _by_location(None)
    return rows, "children", False


def _node_display_name(node: Any) -> str:
    """Prefer package/display name in attributes over raw ``Node.name`` (align with ``find``)."""
    a = dict(getattr(node, "attributes", None) or {})
    s = str(a.get("display_name") or getattr(node, "name", None) or "").strip()
    return s or "?"


def _nodes_by_attr_in_package(
    session: Any,
    *,
    type_code: str,
    attr_key: str,
    attr_value: str,
    world_id: str = "",
) -> List[Any]:
    """
    Narrow fallback queries by JSON attribute (``building_id`` / ``floor_id``) + optional ``world_id``.

    Uses ``Node.attributes[...].astext`` (PostgreSQL JSONB). On failure, falls back to a
    type-scoped ORM list filtered in-Python (non-Postgres or odd JSON adapters).
    """
    from app.models.graph import Node

    v = str(attr_value or "").strip()
    if not v:
        return []
    w = str(world_id or "").strip()
    try:
        q = session.query(Node).filter(
            Node.type_code == type_code,
            Node.is_active == True,  # noqa: E712
            Node.attributes[attr_key].astext == v,
        )
        if w:
            q = q.filter(Node.attributes["world_id"].astext == w)
        return list(q.order_by(Node.id).all())
    except Exception:
        acc: List[Any] = []
        q2 = (
            session.query(Node)
            .filter(Node.type_code == type_code, Node.is_active == True)  # noqa: E712
            .order_by(Node.id)
        )
        for n in q2.all():
            a = dict(n.attributes or {})
            if str(a.get(attr_key) or "") != v:
                continue
            if w and str(a.get("world_id") or "").strip() != w:
                continue
            acc.append(n)
        return acc


def _format_table_row(cols: List[str], widths: List[int]) -> str:
    parts: List[str] = []
    for c, w in zip(cols, widths):
        parts.append(str(c)[:w].ljust(w))
    return "  ".join(parts)


class SpaceCommand(SystemCommand):
    def __init__(self) -> None:
        super().__init__(
            "space",
            "Query spatial (SPACE) node summary: appearance, occupants, devices, relations",
            [],
        )

    def get_usage(self) -> str:
        return "space -t | space -i <node_id>"

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        from app.commands.i18n.locale_text import resolve_locale
        from app.models.graph import Node, NodeType

        loc = resolve_locale(context)
        session = getattr(context, "db_session", None)
        if session is None:
            return CommandResult.error_result(
                _t(loc, "error.no_session", "requires an active DB session")
            )

        p = parse_space_args(args)
        if not p.ok:
            if p.error_key == "error.unknown_flag" and p.error_tokens:
                msg = _t(
                    loc,
                    p.error_key,
                    "unknown flag: {token}",
                    token=p.error_tokens.get("token", "?"),
                )
            else:
                msg = _t(
                    loc,
                    p.error_key or "usage",
                    self.get_usage(),
                )
            return CommandResult.error_result(msg, is_usage=True)

        if p.mode == "usage":
            return CommandResult.error_result(
                _t(loc, "usage.line", self.get_usage()),
                is_usage=True,
            )

        if p.mode == "types":
            codes = _list_space_type_codes(session)
            if not codes:
                return CommandResult.success_result(
                    _t(loc, "type_list.empty", "(no SPACE node types)"),
                    data={"type_codes": []},
                )
            title = _t(loc, "type_list.title", "SPACE type_code")
            lines = [title, "=" * 32]
            for c in codes:
                lines.append(c)
            lines.append(_t(loc, "type_list.footer", "total: {n}").format(n=len(codes)))
            return CommandResult.success_result(
                "\n".join(lines),
                data={"type_codes": codes},
            )

        assert p.node_id is not None
        node = (
            session.query(Node)
            .filter(Node.id == int(p.node_id), Node.is_active == True)  # noqa: E712
            .first()
        )
        if node is None or not _node_space_trait(session, node):
            return CommandResult.error_result(
                _t(loc, "error.not_found", "node not found or not a space")
            )

        nt = session.query(NodeType).filter(NodeType.id == node.type_id).first()
        ntype_name = (getattr(nt, "type_code", None) or node.type_code or "?").strip()

        # Section 1
        s1_lines = self._section1_lines(session, node, ntype_name, loc)
        occ = _rows_occupants(session, int(node.id))
        dev = _rows_devices(session, int(node.id))
        s2_rows, s2_data = self._section_occupants(occ, loc)
        s3_rows, s3_data = self._section_devices(dev, loc)
        s4_rows, s4_data, s4_mode, s4_fb = self._section4(
            session, node, ntype_name, loc
        )

        titles = [
            _t(loc, "section.title.1", "Space description:"),
            _t(loc, "section.title.2", "Space occupants:"),
            _t(loc, "section.title.3", "Space devices:"),
            _t(loc, "section.title.4", "Space relations:"),
        ]
        msg_parts: List[str] = [
            f"{titles[0]}\n" + ("\n".join(s1_lines) if s1_lines else "-"),
            f"\n{titles[1]}\n" + ("\n".join(s2_rows) if s2_rows else _t(loc, "empty.row", "-")),
            f"\n{titles[2]}\n" + ("\n".join(s3_rows) if s3_rows else _t(loc, "empty.row", "-")),
            f"\n{titles[3]}\n" + ("\n".join(s4_rows) if s4_rows else _t(loc, "empty.row", "-")),
        ]
        message = "\n".join(msg_parts)

        s1_text = "\n".join(s1_lines) if s1_lines else ""
        data: Dict[str, Any] = {
            "space_node": {
                "id": int(node.id),
                "type_code": str(node.type_code or ""),
                "name": str(node.name or ""),
                "parent_id": int(node.location_id) if node.location_id else None,
            },
            "section1_appearance": {"message_fragment": s1_text, "lines": s1_lines},
            "section2_occupants": s2_data,
            "section3_devices": s3_data,
            "section4_next_or_adjacent": s4_data,
            "section4_mode": s4_mode,
            "section4_fallback": s4_fb,
        }
        return CommandResult.success_result(message, data=data)

    def _section1_lines(
        self, session: Any, node: Any, ntype: str, loc: str
    ) -> List[str]:
        attrs = dict(node.attributes or {})
        lines: List[str] = []
        head = str(attrs.get("display_name") or node.name or "").strip()

        def _name_line() -> None:
            if head:
                lines.append(_t(loc, "s1.name", "name: {n}", n=head))

        if ntype == "building":
            _name_line()
            bn = str(attrs.get("building_name") or "").strip()
            if bn and bn != head:
                lines.append(_t(loc, "s1.local_name", "also known: {n}", n=bn))
            tgl = str(attrs.get("building_tagline") or "").strip()
            if tgl:
                lines.append(_t(loc, "s1.tagline", "tagline: {n}", n=tgl))
            bshort = str(attrs.get("building_short_description") or "").strip()
            if bshort:
                lines.append(_t(loc, "s1.short_desc", "short: {n}", n=bshort))
            dlong = (node.description or attrs.get("building_description") or "").strip()
            for chunk in dlong.splitlines()[:20] if dlong else ():
                c = str(chunk).strip()
                if c:
                    lines.append(c)
            return lines

        if ntype == "building_floor":
            _name_line()
            fnm = str(attrs.get("floor_name") or "").strip()
            if fnm and fnm != head:
                lines.append(_t(loc, "s1.floor_name", "floor: {n}", n=fnm))
            fshort = str(attrs.get("floor_short_description") or "").strip()
            if fshort:
                lines.append(_t(loc, "s1.short_desc", "short: {n}", n=fshort))
            dlong = (node.description or attrs.get("floor_description") or "").strip()
            for chunk in dlong.splitlines()[:20] if dlong else ():
                c = str(chunk).strip()
                if c:
                    lines.append(c)
            return lines

        if ntype == "world":
            _name_line()
            wtxt = (node.description or attrs.get("description") or "").strip()
            for chunk in str(wtxt).splitlines()[:20]:
                c = str(chunk).strip()
                if c:
                    lines.append(c)
            return lines

        if ntype == "room":
            _name_line()
            d1 = (node.description or attrs.get("room_description") or "").strip()
            for chunk in d1.splitlines()[:20] if d1 else ():
                c = str(chunk).strip()
                if c:
                    lines.append(c)
            amb = str(attrs.get("room_ambiance") or "").strip()
            if amb:
                lines.append(amb)
            for e in connects_to_exits_from_room(session, int(node.id)):
                d = str(e.get("direction") or "")
                tdn = str(e.get("target_display_name") or "")
                lines.append(
                    _t(
                        loc,
                        "s1.exit",
                        "exit {dir}: {name}",
                        dir=d,
                        name=tdn,
                    )
                )
            return lines

        _name_line()
        ddef = (node.description or attrs.get("room_description") or attrs.get("building_description") or attrs.get("floor_description") or "").strip()
        for chunk in ddef.splitlines()[:20] if ddef else ():
            c = str(chunk).strip()
            if c:
                lines.append(c)
        return lines

    def _section_occupants(
        self, nodes: List[Any], loc: str
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        if not nodes:
            return [], []
        h_id = _t(loc, "table.header.id", "id")
        h_name = _t(loc, "table.header.name", "name")
        h_type = _t(loc, "table.header.type_code", "type_code")
        widths = [8, 28, 16]
        head = _format_table_row([h_id, h_name, h_type], widths)
        sep = "  ".join("-" * w for w in widths)
        rows: List[str] = [head, sep]
        data: List[Dict[str, Any]] = []
        for n in nodes:
            dname = _node_display_name(n)
            data.append(
                {
                    "id": int(n.id),
                    "name": dname,
                    "type_code": str(n.type_code or ""),
                }
            )
            rows.append(
                _format_table_row(
                    [str(n.id), dname, str(n.type_code or "")], widths
                )
            )
        return rows, data

    def _section_devices(
        self, nodes: List[Any], loc: str
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        if not nodes:
            return [], []
        h_id = _t(loc, "table.header.id", "id")
        h_name = _t(loc, "table.header.name", "name")
        h_st = _t(loc, "table.header.status", "status")
        widths = [8, 28, 20]
        head = _format_table_row([h_id, h_name, h_st], widths)
        sep = "  ".join("-" * w for w in widths)
        rows: List[str] = [head, sep]
        data: List[Dict[str, Any]] = []
        for n in nodes:
            a = dict(n.attributes or {})
            st = str(
                a.get("status")
                or a.get("operational_status")
                or a.get("device_status")
                or "-"
            )
            dname = _node_display_name(n)
            data.append({"id": int(n.id), "name": dname, "status": st})
            rows.append(
                _format_table_row([str(n.id), dname, st], widths)
            )
        return rows, data

    def _section4(
        self, session: Any, node: Any, ntype: str, loc: str
    ) -> Tuple[List[str], List[Dict[str, Any]], str, bool]:
        from app.models.graph import Node

        if ntype == "room":
            ex = connects_to_exits_from_room(session, int(node.id))
            data: List[Dict[str, Any]] = []
            lines: List[str] = []
            widths = [8, 20, 12, 24]
            h_id = _t(loc, "table.header.id", "id")
            h_name = _t(loc, "table.header.name", "name")
            h_dir = _t(loc, "table.header.direction", "direction")
            h_de = _t(loc, "table.header.description", "description")
            head = _format_table_row([h_id, h_name, h_dir, h_de], widths)
            sep = "  ".join("-" * w for w in widths)
            if ex:
                lines.extend([head, sep])
            for e in ex:
                tid = int(e["target_id"])
                tnode = session.query(Node).filter(Node.id == tid).first()
                desc = ""
                if tnode:
                    desc = str(
                        (tnode.description or (tnode.attributes or {}).get("room_short_description") or "")
                    ).strip()[:200]
                name = str(e.get("target_display_name") or "")
                direction = str(e.get("direction") or "")
                drow = {
                    "id": tid,
                    "name": name,
                    "direction": direction,
                    "description": desc,
                }
                data.append(drow)
                lines.append(_format_table_row([str(tid), name, direction, desc], widths))
            return lines, data, "room_links", False

        children, mode, fb = _child_space_nodes(session, node)
        data2: List[Dict[str, Any]] = []
        lines2: List[str] = []
        widths2 = [8, 24, 36]
        h_id = _t(loc, "table.header.id", "id")
        h_name = _t(loc, "table.header.name", "name")
        h_de = _t(loc, "table.header.description", "description")
        head2 = _format_table_row([h_id, h_name, h_de], widths2)
        sep2 = "  ".join("-" * w for w in widths2)
        if children:
            lines2.extend([head2, sep2])
        for c in children:
            a = dict(c.attributes or {})
            desc = str(c.description or a.get("room_short_description") or a.get("floor_short_description") or "").strip()[:200]
            cname = _node_display_name(c)
            data2.append(
                {
                    "id": int(c.id),
                    "name": cname,
                    "direction": None,
                    "description": desc,
                }
            )
            lines2.append(
                _format_table_row([str(c.id), cname, desc], widths2)
            )
        return lines2, data2, mode, fb
