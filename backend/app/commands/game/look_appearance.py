"""Evennia-style room/object appearance assembly for Look."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.commands.game.look_template_format import safe_format_template

CAMPUSWORLD_ROOM_APPEARANCE_TEMPLATE = """
{header}
{name}{extra_name_info}
{desc}
{exits}
{portals}
{fixtures}
{characters}
{things}
{footer}
""".strip()

DEFAULT_OBJECT_LOOK_TEMPLATE = """
*{name}*{extra_name_info}
{desc}
{footer}
""".strip()


def compress_whitespace(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [ln.rstrip() for ln in text.splitlines()]
    return "\n".join(lines)


def format_appearance(text: str) -> str:
    return compress_whitespace(text).strip()


def _bucket_for_entry(type_code: str, attrs: Dict[str, Any]) -> str:
    tc = (type_code or "").lower()
    ek = str(attrs.get("entity_kind") or "").lower()
    if tc == "world_entrance":
        return "world_exits"
    if ek == "portal" or tc == "world":
        return "portals"
    if ek == "fixture" or tc == "system_bulletin_board":
        return "fixtures"
    if tc in ("character", "npc_agent") or ek == "character":
        return "characters"
    return "things"


def _format_exits_block(exits: List[str], exit_entries: Optional[List[Dict[str, Any]]] = None) -> str:
    rows: List[str] = []
    exit_entries = list(exit_entries or [])
    if exit_entries:
        by_dir: Dict[str, List[Dict[str, Any]]] = {}
        for e in exit_entries:
            if not isinstance(e, dict):
                continue
            d = str(e.get("direction") or "").strip()
            if not d:
                continue
            by_dir.setdefault(d, []).append(e)
        for d in sorted(by_dir.keys()):
            group = by_dir[d]
            if len(group) == 1:
                target = str(group[0].get("target_display_name") or group[0].get("target_package_node_id") or "?").strip()
                short = str(group[0].get("target_short_desc") or "").strip()
                if short:
                    rows.append(f"- {d} -> {target}（{short}）")
                else:
                    rows.append(f"- {d} -> {target}")
            else:
                targets = " / ".join(
                    str(x.get("target_display_name") or x.get("target_package_node_id") or "?").strip() for x in group
                )
                rows.append(f"- {d} -> [{len(group)} destinations] {targets}")
    if rows:
        return "出口：\n" + "\n".join(rows)
    if not exits:
        return ""
    return "出口：" + ", ".join(str(e) for e in exits if e)


def _instantiate_for_look(type_code: str, entry: Dict[str, Any]):
    from app.models import model_factory

    cls = model_factory.get_model(type_code or "")
    if not cls:
        return None
    name = entry.get("name") or type_code or "?"
    desc = str(entry.get("description") or "")
    attrs = dict(entry.get("attributes") or {})
    try:
        return cls(name=name, description=desc, attributes=attrs, disable_auto_sync=True)
    except TypeError:
        pass
    try:
        return cls(name=name, disable_auto_sync=True)
    except Exception:
        return None


def short_label_from_scoped_title(name: str, attrs: Dict[str, Any]) -> Optional[str]:
    """If title uses ``Place · Short`` (HiCampus display_name_tpl), return the short segment."""
    for cand in (
        str(name or "").strip(),
        str(attrs.get("display_name") or "").strip(),
    ):
        if " · " in cand:
            tail = cand.rsplit(" · ", 1)[-1].strip()
            if tail and tail != cand:
                return tail
    return None


def look_alias_strings_from_attrs(attrs: Dict[str, Any]) -> List[str]:
    """Human-entered aliases for look matching (flat + legacy nested ``attributes.attributes``)."""
    a = dict(attrs or {})
    inner = a.get("attributes")
    inner_d: Dict[str, Any] = inner if isinstance(inner, dict) else {}
    keys = ("room_list_name", "look_list_name", "short_name", "display_name")
    out: List[str] = []
    for d in (a, inner_d):
        for k in keys:
            v = d.get(k)
            if isinstance(v, str) and v.strip():
                out.append(v.strip())
        tail = short_label_from_scoped_title("", d)
        if tail:
            out.append(tail)
    return out


def room_list_label_for_entry(entry: Dict[str, Any]) -> str:
    """Short label for room lists / disambiguation (aligns with ``get_room_list_display_name``)."""
    tc = str(entry.get("type_code") or entry.get("type") or "")
    inst = _instantiate_for_look(tc, entry)
    if inst is not None and hasattr(inst, "get_room_list_display_name"):
        try:
            return inst.get_room_list_display_name()
        except Exception:
            pass
    attrs = dict(entry.get("attributes") or {})
    inner = attrs.get("attributes")
    if isinstance(inner, dict):
        for key in ("room_list_name", "look_list_name", "short_name"):
            v = inner.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    for key in ("room_list_name", "look_list_name", "short_name"):
        v = attrs.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    scoped = short_label_from_scoped_title(str(entry.get("name") or ""), attrs)
    if scoped:
        return scoped
    return str(entry.get("name") or "?")


def content_line_for_entry(entry: Dict[str, Any]) -> str:
    tc = str(entry.get("type_code") or entry.get("type") or "")
    inst = _instantiate_for_look(tc, entry)
    if inst is not None and hasattr(inst, "room_list_line_for_look"):
        try:
            return inst.room_list_line_for_look()
        except Exception:
            pass
    name = entry.get("name") or "?"
    return f"- *{name}*"


def _lines_block(entries: List[Dict[str, Any]], title: str) -> str:
    if not entries:
        return ""
    lines = [content_line_for_entry(e) for e in entries]
    lines = [ln for ln in lines if ln]
    if not lines:
        return ""
    if title:
        return f"{title}\n" + "\n".join(lines)
    return "\n".join(lines)


def return_appearance_room(room: Dict[str, Any], context: Any = None) -> str:
    del context  # reserved for looker permissions / future use
    attrs_root: Dict[str, Any] = {}
    if isinstance(room.get("room_node_attributes"), dict):
        attrs_root = room["room_node_attributes"]

    tmpl = str(room.get("appearance_template") or attrs_root.get("appearance_template") or "").strip()
    if not tmpl:
        tmpl = CAMPUSWORLD_ROOM_APPEARANCE_TEMPLATE

    name = str(room.get("name") or "未知房间")
    extra = str(room.get("extra_name_info") or attrs_root.get("extra_name_info") or "").strip()
    if extra and not extra.startswith(("（", "(")):
        extra = f"（{extra}）"

    desc_parts: List[str] = []
    if (room.get("short_description") or "").strip():
        desc_parts.append(str(room["short_description"]).strip())
    desc_parts.append(str(room.get("description") or "这里没有什么特别的。").strip())
    if (room.get("ambiance") or "").strip():
        desc_parts.append(f"氛围：{str(room['ambiance']).strip()}")
    desc = "\n\n".join(p for p in desc_parts if p)

    direction_exits = list(room.get("exits") or [])
    exits_block = _format_exits_block(direction_exits, room.get("exit_entries") or [])

    buckets: Dict[str, List[Dict[str, Any]]] = {
        "portals": [],
        "world_exits": [],
        "fixtures": [],
        "characters": [],
        "things": [],
    }
    for entry in list(room.get("content_entries") or []):
        if not isinstance(entry, dict):
            continue
        tc = str(entry.get("type_code") or entry.get("type") or "")
        a = dict(entry.get("attributes") or {})
        b = _bucket_for_entry(tc, a)
        buckets[b].append(entry)

    portals = _lines_block(buckets["portals"], "入口/传送：")
    world_exits_lines = _lines_block(buckets["world_exits"], "")
    if world_exits_lines.strip():
        world_exits_section = "出口（世界）：\n" + world_exits_lines.strip()
        if exits_block.strip():
            exits_block = exits_block.strip() + "\n\n" + world_exits_section
        else:
            exits_block = world_exits_section
    fixtures = _lines_block(buckets["fixtures"], "陈设：")
    characters = _lines_block(buckets["characters"], "人物：")
    things = _lines_block(buckets["things"], "物品：")

    footer_parts: List[str] = []
    rs = str(room.get("room_status") or "").strip()
    if rs:
        footer_parts.append(rs)
    op = room.get("other_players") or []
    if op:
        footer_parts.append("其他玩家: " + ", ".join(str(x) for x in op))
    footer = "\n\n".join(footer_parts) if footer_parts else ""

    kwargs = {
        "header": "",
        "name": name,
        "extra_name_info": extra,
        "desc": desc,
        "exits": exits_block,
        "portals": portals,
        "fixtures": fixtures,
        "characters": characters,
        "things": things,
        "footer": footer,
    }
    text = safe_format_template(tmpl, **kwargs)
    return format_appearance(text)


def return_appearance_object(
    context: Any,
    obj: Dict[str, Any],
    target_args: Optional[List[str]] = None,
) -> str:
    del target_args  # handled by get_appearance on models that need it
    tc = str(obj.get("type_code") or obj.get("type") or "")
    attrs = dict(obj.get("attributes") or {})
    from app.models import model_factory

    model_cls = model_factory.get_model(tc)
    inst = None
    if model_cls:
        try:
            inst = model_cls(
                name=obj.get("name", tc),
                description=str(obj.get("description") or ""),
                attributes=attrs,
                disable_auto_sync=True,
            )
        except TypeError:
            try:
                inst = model_cls(name=obj.get("name", tc), disable_auto_sync=True)
            except Exception:
                inst = None

    if inst is not None:
        # Examine header: full display name (Evennia-style); room list still uses get_room_list_display_name.
        name = inst.get_display_name(looker=context)
        extra = inst.get_display_extra_name_info(looker=context)
        desc = str(inst.get_display_desc(looker=context) or "").strip()
        if not desc:
            desc = "这看起来没什么特别的。"
    else:
        attrs_ln = str(attrs.get("room_list_name") or "").strip()
        name = attrs_ln or str(obj.get("name") or obj.get("id") or "未知")
        extra = ""
        desc = str(
            obj.get("description")
            or attrs.get("long_description")
            or attrs.get("short_description")
            or attrs.get("description")
            or attrs.get("entry_description")
            or attrs.get("look_description")
            or attrs.get("examine_desc")
            or ""
        ).strip()
        inner = attrs.get("attributes")
        if not desc and isinstance(inner, dict):
            desc = str(
                inner.get("long_description")
                or inner.get("short_description")
                or inner.get("description")
                or inner.get("look_description")
                or inner.get("examine_desc")
                or ""
            ).strip()
        if not desc:
            disp = str(attrs.get("display_name") or "").strip()
            if disp and disp != name:
                desc = disp
        if not desc:
            desc = "这看起来没什么特别的。"

    footer = ""
    if tc == "world_entrance":
        wid = str(attrs.get("portal_world_id") or attrs.get("world_id") or name).lower()
        if wid:
            footer = f"提示: 输入 'enter {wid}' 进入该世界。"
    elif tc == "world":
        wid = str(attrs.get("world_id") or name).lower()
        if wid:
            footer = f"提示: 输入 'enter {wid}' 进入该世界。"

    cite: List[str] = []
    ref_name = str(obj.get("name") or "").strip()
    if ref_name:
        cite.append(f"引用: {ref_name}")
    disp = str(attrs.get("display_name") or "").strip()
    if disp and disp != ref_name:
        cite.append(f"别名: {disp}")
    pkg = str(attrs.get("package_node_id") or "").strip()
    if pkg:
        cite.append(f"包内节点: {pkg}")
    nid = obj.get("node_id")
    if nid is not None:
        cite.append(f"节点 id: {nid}")

    tail_parts: List[str] = []
    if cite:
        tail_parts.append("\n".join(cite))
    tail_parts.append(f"类型: {tc or '未知'}")
    loc = obj.get("location")
    if loc and str(loc) != "未知位置":
        tail_parts.append(f"位置: {loc}")

    body = safe_format_template(
        DEFAULT_OBJECT_LOOK_TEMPLATE,
        name=name,
        extra_name_info=extra,
        desc=desc,
        footer=footer,
    )
    text = body + ("\n\n" + "\n".join(tail_parts) if tail_parts else "")
    return format_appearance(text)
