"""Agent-facing commands: capabilities, tools, AICO shorthand, and agent directory."""

from __future__ import annotations

import json
import threading
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.commands.agent_command_context import command_context_for_npc_agent
from app.commands.base import CommandContext, CommandResult, SystemCommand
from app.commands.registry import command_registry
from app.commands.npc_agent_resolve import (
    enabled_allows,
    normalize_handle,
    resolve_npc_agent_by_handle,
)
from app.core.permissions import permission_checker
from app.models.graph import Node, NodeType
from app.models.system import AgentRunRecord

AGENT_TOOLS_FORBIDDEN = "AGENT_TOOLS_FORBIDDEN"
AGENT_TOOLS_MISORDERED = "AGENT_TOOLS_MISORDERED"
AGENT_TOOLS_UNKNOWN_TOOL = "AGENT_TOOLS_UNKNOWN_TOOL"
AGENT_TOOLS_MANAGE_PERMISSION = "admin.agent.tools.manage"
_AGENT_TOOLS_WRITE_SUBCOMMANDS = {"add", "del"}

# Unified user-facing message when status lookup must not distinguish missing vs inaccessible agents.
AGENT_STATUS_ACCESS_ERROR = "agent not found or not accessible"


def derive_agent_status(node: Node, session: Session) -> str:
    """Return agent row status: unavailable | idle | working (from node attributes and run records)."""
    if not node.is_active:
        return "unavailable"
    attrs = dict(node.attributes or {})
    if not enabled_allows(attrs):
        return "unavailable"
    running = (
        session.query(AgentRunRecord)
        .filter(
            AgentRunRecord.agent_node_id == node.id,
            AgentRunRecord.ended_at.is_(None),
            AgentRunRecord.status == "running",
        )
        .first()
    )
    if running is not None:
        return "working"
    return "idle"


def _service_id_display(node: Node) -> str:
    attrs = dict(node.attributes or {})
    raw = str(attrs.get("service_id") or "").strip()
    return raw or str(node.id)


def _query_active_npc_agent_nodes(session: Session) -> List[Node]:
    return (
        session.query(Node)
        .filter(
            Node.type_code == "npc_agent",
            Node.is_active == True,  # noqa: E712
        )
        .order_by(Node.id)
        .all()
    )


def _find_npc_agent_nodes_by_handle(session: Session, handle: str) -> List[Node]:
    """Match service_id or handle_aliases (same as resolve); includes disabled agents."""
    h = normalize_handle(handle)
    if not h:
        return []
    matches: List[Node] = []
    seen: set[int] = set()
    for n in _query_active_npc_agent_nodes(session):
        attrs = dict(n.attributes or {})
        sid = str(attrs.get("service_id") or "").strip().lower()
        matched = sid == h
        if not matched:
            raw = attrs.get("handle_aliases")
            if isinstance(raw, list):
                for a in raw:
                    if str(a).strip().lower() == h:
                        matched = True
                        break
        if matched:
            if n.id not in seen:
                seen.add(n.id)
                matches.append(n)
    return matches


def _agent_row_dict(node: Node, session: Session) -> Dict[str, Any]:
    return {
        "service_id": _service_id_display(node),
        "name": node.name or "",
        "status": derive_agent_status(node, session),
        "agent_node_id": node.id,
    }


def _agent_list_text(locale: str, key_path: str, default: str) -> str:
    from app.commands.i18n.command_resource import get_command_i18n_text

    return get_command_i18n_text("agent", key_path, locale, default)


def _format_agent_list_message(rows: List[Dict[str, Any]], locale: str) -> str:
    """Tabular `agent list` output for SSH (result.message), aligned with `world list` / `agent_tools` layout."""
    if not rows:
        return _agent_list_text(
            locale,
            "list.empty",
            "agent list: no active npc_agent nodes found.\n"
            "Expected: nodes with type_code=npc_agent, is_active=true",
        )

    def status_label(machine: str) -> str:
        m = (machine or "").strip().lower()
        if not m:
            return machine or "-"
        return _agent_list_text(
            locale,
            f"status_value.{m}",
            machine,
        )

    h_sid = _agent_list_text(locale, "list.header.service_id", "service_id")
    h_name = _agent_list_text(locale, "list.header.name", "name")
    h_status = _agent_list_text(locale, "list.header.status", "status")
    h_id = _agent_list_text(locale, "list.header.id", "agent_node_id")
    sid_w, name_w, status_w, id_w = 16, 26, 14, 12
    lines: List[str] = [
        f"{h_sid:<{sid_w}} {h_name:<{name_w}} {h_status:<{status_w}} {h_id}",
        "-" * (sid_w + name_w + status_w + id_w + 3),
    ]
    for r in rows:
        sid = str(r.get("service_id", ""))[:sid_w]
        name = str(r.get("name") or "-")[:name_w]
        st = str(status_label(str(r.get("status", ""))))[:status_w]
        aid = str(r.get("agent_node_id", ""))[:id_w]
        lines.append(f"{sid:<{sid_w}} {name:<{name_w}} {st:<{status_w}} {aid}")
    lines.append("")
    lines.append(_agent_list_text(locale, "list.footer", "(total={n})").format(n=len(rows)))
    hint = _agent_list_text(locale, "list.hint", "").strip()
    if hint:
        lines.append(hint)
    return "\n".join(lines)


class AgentCapabilitiesCommand(SystemCommand):
    """List static capabilities for an agent instance."""

    def __init__(self):
        super().__init__(
            "agent_capabilities",
            "List agent capabilities for a service_id",
            ["agent.capabilities"],
        )

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result("usage: agent_capabilities <service_id>")
        if not context.db_session:
            return CommandResult.error_result("database session required")
        sid = args[0]
        node, rerr = resolve_npc_agent_by_handle(context.db_session, sid)
        if rerr:
            return CommandResult.error_result(rerr)
        nt = context.db_session.query(NodeType).filter(NodeType.id == node.type_id).first()
        typeclass = nt.typeclass if nt else None
        data = {
            "service_id": sid,
            "agent_node_id": node.id,
            "typeclass": typeclass,
            "decision_mode": (node.attributes or {}).get("decision_mode"),
            "cognition": (node.attributes or {}).get("cognition_profile_ref"),
            "capabilities": [
                "command.execute",
                "agent.memory",
            ],
        }
        return CommandResult.success_result(json.dumps(data, ensure_ascii=False))


def _normalize_allowlist_to_primary(entries: Any) -> List[str]:
    """Normalize a stored ``tool_allowlist`` to **primary** command names.

    Mirrors ``resolved_tool_surface._normalize_allowlist``: aliases resolve
    to their registered primary, unknown spellings are dropped, and order
    is preserved with deduplication.
    """
    if not isinstance(entries, list):
        return []
    out: List[str] = []
    seen: set = set()
    for raw in entries:
        if not isinstance(raw, str):
            continue
        cmd = command_registry.get_command(raw)
        primary = cmd.name if cmd is not None else raw
        if primary in seen:
            continue
        seen.add(primary)
        out.append(primary)
    return out


def _resolve_tool_to_primary(name: str) -> Optional[str]:
    """Return the primary command name for ``name`` (or alias), or ``None`` if unknown."""
    cmd = command_registry.get_command(name)
    return cmd.name if cmd is not None else None


def _effective_tools_for_agent(
    session: Session, node: Node, invoker: CommandContext
) -> List[str]:
    """Return the same tool id list as ``agent_tools <service_id>`` (single-agent path).

    This is **RegistryToolExecutor** + **ToolRouter** on
    ``command_context_for_npc_agent`` — i.e.  ``tool_allowlist`` (if any)
    intersected with **policy-allowed** commands (``get_available_commands`` on
    the tool context), matching runtime agent execution. Also used for the
    per-row ``tools`` column in the no-arg list so it cannot diverge from
    the single-agent JSON output.
    """
    from app.game_engine.agent_runtime.resolved_tool_surface import _normalize_allowlist
    from app.game_engine.agent_runtime.tooling import RegistryToolExecutor, ToolRouter

    raw = (node.attributes or {}).get("tool_allowlist") or []
    # Match ``build_resolved_tool_surface`` / F08: aliases (e.g. ``locate``) →
    # primary names before ``ToolRouter`` filter, which compares against
    # ``list_tool_ids`` (primaries only).
    entries = [str(x) for x in raw] if isinstance(raw, list) else []
    allowlist = _normalize_allowlist(entries)
    actx = command_context_for_npc_agent(session, node, invoker)
    router = ToolRouter(allowlist=allowlist or [])
    ex = RegistryToolExecutor()
    return list(router.filter(ex.list_tool_ids(actx, allowlist=None)))


def _excluded_by_policy_on_allowlist(
    node: Node, effective: List[str]
) -> List[str]:
    """Names present in a normalized, registered allowlist that policy denies on the tool surface.

    Filled only for diagnostics: ``excluded`` = registered primary names
    that appear in ``tool_allowlist`` (after ``get_command`` resolution) but
    not in ``effective``.
    """
    raw = (node.attributes or {}).get("tool_allowlist") or []
    primaries = _normalize_allowlist_to_primary(raw)
    registered = [p for p in primaries if command_registry.get_command(p) is not None]
    eff = set(effective)
    return sorted(p for p in registered if p not in eff)


def _agent_tools_text(locale: str, key_path: str, default: str) -> str:
    """Resolve ``commands.agent_tools.*`` locale text via the shared helper."""
    from app.commands.i18n.command_resource import get_command_i18n_text

    return get_command_i18n_text("agent_tools", key_path, locale, default)


def _truncate_tools_cell(tools: List[str], width: int, locale: str) -> str:
    """Render tool list for the table cell, truncating with ``…`` to fit ``width``."""
    if not tools:
        return _agent_tools_text(locale, "tools_empty", "(none)")
    joined = ", ".join(tools)
    if len(joined) <= width:
        return joined
    # Reserve one character for the ellipsis.
    cap = max(1, width - 1)
    return joined[:cap].rstrip(", ") + "\u2026"


def _format_agent_tools_table(rows: List[Dict[str, Any]], locale: str) -> str:
    """Multi-line table for the no-arg ``agent_tools`` form.

    Mirrors ``world list``'s ``_format_world_list_message`` shape: header,
    separator, fixed-width rows, blank line, and a ``(total=N)`` footer.
    """
    if not rows:
        return _agent_tools_text(locale, "empty", "No agents registered.")
    h_sid = _agent_tools_text(locale, "header.service_id", "service_id")
    h_name = _agent_tools_text(locale, "header.name", "name")
    h_status = _agent_tools_text(locale, "header.status", "status")
    h_n = _agent_tools_text(locale, "header.n_tools", "n")
    h_tools = _agent_tools_text(locale, "header.tools", "tools")
    sid_w, name_w, status_w, n_w, tools_w = 16, 20, 12, 4, 60
    lines = [
        f"{h_sid:<{sid_w}} {h_name:<{name_w}} {h_status:<{status_w}} {h_n:<{n_w}}  {h_tools}",
        "-" * (sid_w + name_w + status_w + n_w + tools_w + 5),
    ]
    for r in rows:
        sid = str(r.get("service_id", ""))[:sid_w]
        name = str(r.get("name") or "-")[:name_w]
        status = str(r.get("status") or "-")[:status_w]
        n = str(r.get("tool_count", 0))[:n_w]
        tools_cell = _truncate_tools_cell(list(r.get("tools") or []), tools_w, locale)
        lines.append(f"{sid:<{sid_w}} {name:<{name_w}} {status:<{status_w}} {n:<{n_w}}  {tools_cell}")
    lines.append("")
    footer = _agent_tools_text(locale, "footer.total", "(total={n})").format(n=len(rows))
    lines.append(footer)
    return "\n".join(lines)


def _apply_allowlist_change(
    node: Node,
    *,
    action: str,
    requested: List[str],
) -> Tuple[List[str], List[str], List[str], List[str]]:
    """Mutate ``node.attributes['tool_allowlist']`` and report the diff.

    Returns ``(new_list, added, removed, unchanged)`` where ``new_list`` is
    the normalized primary-name list written back into the attribute. The
    caller is responsible for ``flag_modified`` + ``commit``.

    Idempotent: ``add`` of an existing tool counts as ``unchanged``;
    ``del`` of a missing tool counts as ``unchanged``. Duplicate
    requested entries are de-duplicated before applying.
    """
    attrs = dict(node.attributes or {})
    current = _normalize_allowlist_to_primary(attrs.get("tool_allowlist") or [])
    seen_req: set = set()
    deduped: List[str] = []
    for r in requested:
        if r in seen_req:
            continue
        seen_req.add(r)
        deduped.append(r)

    added: List[str] = []
    removed: List[str] = []
    unchanged: List[str] = []
    new_list = list(current)
    if action == "add":
        existing = set(new_list)
        for tool in deduped:
            if tool in existing:
                unchanged.append(tool)
                continue
            new_list.append(tool)
            existing.add(tool)
            added.append(tool)
    else:
        existing = set(new_list)
        to_remove = set()
        for tool in deduped:
            if tool not in existing:
                unchanged.append(tool)
                continue
            to_remove.add(tool)
            removed.append(tool)
        if to_remove:
            new_list = [t for t in new_list if t not in to_remove]

    attrs["tool_allowlist"] = new_list
    node.attributes = attrs
    return new_list, added, removed, unchanged


def _join_tool_names(names: List[str]) -> str:
    return ", ".join(names) if names else ""


def _format_agent_tools_write_message(
    locale: str,
    *,
    action: str,
    service_id: str,
    added: List[str],
    removed: List[str],
    unchanged: List[str],
) -> str:
    """User-facing one-line result for ``add`` / ``del`` (i18n, tool names, not only counts)."""
    sid = service_id

    if action == "add":
        if added and not unchanged:
            return _agent_tools_text(
                locale,
                "summary.add_success",
                "add {sid} {tools} succeeded (allowlist updated).",
            ).format(sid=sid, tools=_join_tool_names(added))
        if added and unchanged:
            return _agent_tools_text(
                locale,
                "summary.add_mixed",
                (
                    "add {sid} {added} succeeded. "
                    "Already in allowlist (no change): {unchanged}."
                ),
            ).format(
                sid=sid, added=_join_tool_names(added), unchanged=_join_tool_names(unchanged)
            )
        return _agent_tools_text(
            locale,
            "summary.add_noop",
            "No change: {tools} already in allowlist for {sid}.",
        ).format(sid=sid, tools=_join_tool_names(unchanged))

    # del
    if removed and not unchanged:
        return _agent_tools_text(
            locale,
            "summary.del_success",
            "del {sid} {tools} succeeded (allowlist updated).",
        ).format(sid=sid, tools=_join_tool_names(removed))
    if removed and unchanged:
        return _agent_tools_text(
            locale,
            "summary.del_mixed",
            (
                "del {sid} {removed} succeeded. "
                "Not in allowlist (no change): {unchanged}."
            ),
        ).format(
            sid=sid, removed=_join_tool_names(removed), unchanged=_join_tool_names(unchanged)
        )
    return _agent_tools_text(
        locale,
        "summary.del_noop",
        "No change: {tools} not in allowlist for {sid}.",
    ).format(sid=sid, tools=_join_tool_names(unchanged))


class AgentToolsCommand(SystemCommand):
    """List or maintain ``npc_agent`` tool allowlists.

    Routes:

    * ``agent_tools`` (no args): one row per active agent with the
      same effective tool list as ``agent_tools <service_id>`` (see
      ``_effective_tools_for_agent``) — see SPEC §3.
    * ``agent_tools <service_id>``: existing single-agent JSON output
      (preserved for back-compat) plus a structured ``data`` mirror.
    * ``agent_tools add|del <service_id> <tool>...``: idempotent,
      atomic edit of the agent's stored ``attributes.tool_allowlist``;
      gated by ``admin.agent.tools.manage``.
    """

    def __init__(self):
        super().__init__(
            "agent_tools",
            (
                "List every visible agent and its tools (one row per agent), "
                "or query a single agent by service_id. Subcommands `add` / "
                "`del` edit the agent's `attributes.tool_allowlist` and "
                "require `admin.agent.tools.manage`."
            ),
            ["agent.tools"],
        )

    def get_usage(self) -> str:
        return (
            "agent_tools | agent_tools <service_id> | "
            "agent_tools add <service_id> <tool> [<tool>...] | "
            "agent_tools del <service_id> <tool> [<tool>...]"
        )

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        from app.commands.i18n.locale_text import resolve_locale

        loc = resolve_locale(context)
        first = (args[0].strip().lower() if args else "")
        if first in _AGENT_TOOLS_WRITE_SUBCOMMANDS:
            return self._write(context, first, args[1:], loc)
        if not args:
            return self._list_all(context, loc)
        if len(args) >= 2:
            second = args[1].strip().lower()
            if first not in _AGENT_TOOLS_WRITE_SUBCOMMANDS and second in _AGENT_TOOLS_WRITE_SUBCOMMANDS:
                ukey = f"usage.{second}"
                udefault = f"agent_tools {second} <service_id> <tool>..."
                expected = _agent_tools_text(loc, ukey, udefault)
                msg = _agent_tools_text(
                    loc,
                    "error.misordered_add_del",
                    (
                        "The `add` or `del` subcommand must be the first token after `agent_tools`. "
                        "Use: {expected}\n"
                        "(This line was parsed as a query for agent `{first}` only; "
                        "\"{second}\" and following tokens were ignored.)"
                    ),
                ).format(expected=expected, first=args[0], second=second)
                return CommandResult.error_result(msg, error=AGENT_TOOLS_MISORDERED)
        return self._single_agent(context, args[0])

    def _list_all(self, context: CommandContext, locale: str) -> CommandResult:
        if not context.db_session:
            return CommandResult.error_result(
                _agent_tools_text(locale, "error.no_session", "database session required")
            )
        nodes = _query_active_npc_agent_nodes(context.db_session)
        rows: List[Dict[str, Any]] = []
        for node in nodes:
            tools = _effective_tools_for_agent(
                context.db_session, node, context
            )
            excluded = _excluded_by_policy_on_allowlist(node, tools)
            rows.append(
                {
                    "service_id": _service_id_display(node),
                    "name": node.name or "",
                    "status": derive_agent_status(node, context.db_session),
                    "agent_node_id": node.id,
                    "tool_count": len(tools),
                    "tools": tools,
                    "excluded_by_policy": excluded,
                }
            )
        rows.sort(key=lambda r: (r.get("service_id") or "", r.get("name") or ""))
        message = _format_agent_tools_table(rows, locale)
        return CommandResult.success_result(
            message,
            data={"agents": rows, "total": len(rows)},
        )

    def _single_agent(self, context: CommandContext, handle: str) -> CommandResult:
        if not context.db_session:
            return CommandResult.error_result("database session required")
        node, rerr = resolve_npc_agent_by_handle(context.db_session, handle)
        if rerr:
            return CommandResult.error_result(rerr)
        ids = _effective_tools_for_agent(context.db_session, node, context)
        excluded = _excluded_by_policy_on_allowlist(node, ids)
        message = json.dumps({"tools": ids}, ensure_ascii=False)
        return CommandResult.success_result(
            message,
            data={
                "service_id": _service_id_display(node),
                "agent_node_id": node.id,
                "tools": ids,
                "excluded_by_policy": excluded,
            },
        )

    def _write(
        self,
        context: CommandContext,
        action: str,
        rest: List[str],
        locale: str,
    ) -> CommandResult:
        usage_key = f"usage.{action}"
        usage_default = (
            f"agent_tools {action} <service_id> <tool> [<tool>...]"
        )
        usage_msg = _agent_tools_text(locale, usage_key, usage_default)

        if not context.db_session:
            return CommandResult.error_result(
                _agent_tools_text(locale, "error.no_session", "database session required")
            )
        if not permission_checker.check_permission(
            list(context.permissions or []), AGENT_TOOLS_MANAGE_PERMISSION
        ):
            template = _agent_tools_text(
                locale,
                "error.forbidden",
                "Permission denied for agent_tools {action}",
            )
            return CommandResult.error_result(
                template.format(action=action), error=AGENT_TOOLS_FORBIDDEN
            )
        if len(rest) < 2:
            return CommandResult.error_result(usage_msg, is_usage=True)
        handle = rest[0].strip()
        tool_args = [t.strip() for t in rest[1:] if t and t.strip()]
        if not tool_args:
            return CommandResult.error_result(usage_msg, is_usage=True)

        node, rerr = resolve_npc_agent_by_handle(context.db_session, handle)
        if rerr:
            return CommandResult.error_result(rerr)

        primaries: List[str] = []
        for raw in tool_args:
            primary = _resolve_tool_to_primary(raw)
            if primary is None:
                template = _agent_tools_text(
                    locale, "error.unknown_tool", "unknown tool: {name}"
                )
                return CommandResult.error_result(
                    template.format(name=raw), error=AGENT_TOOLS_UNKNOWN_TOOL
                )
            primaries.append(primary)

        new_list, added, removed, unchanged = _apply_allowlist_change(
            node, action=action, requested=primaries
        )
        flag_modified(node, "attributes")
        context.db_session.commit()

        sid = _service_id_display(node)
        message = _format_agent_tools_write_message(
            locale,
            action=action,
            service_id=sid,
            added=added,
            removed=removed,
            unchanged=unchanged,
        )

        return CommandResult.success_result(
            message,
            data={
                "service_id": sid,
                "agent_node_id": node.id,
                "action": action,
                "tool_allowlist": list(new_list),
                "added": added,
                "removed": removed,
                "unchanged": unchanged,
            },
        )


class AicoCommand(SystemCommand):
    """Shorthand for talking to the default assistant AICO."""

    def __init__(self):
        super().__init__("aico", "Talk to default assistant AICO", [])

    def get_usage(self) -> str:
        return "aico <message...>"

    def _get_specific_help(self) -> str:
        return "\nEquivalent to: @aico <message>\n"

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        from app.commands.npc_agent_nlp import assistant_nlp_command_result, run_npc_agent_nlp_tick

        if not args:
            return CommandResult.error_result("usage: aico <message...>")
        if not context.db_session:
            return CommandResult.error_result("database session required")
        message = " ".join(args).strip()
        node, rerr = resolve_npc_agent_by_handle(context.db_session, "aico")
        if rerr:
            return CommandResult.error_result(rerr)
        attrs = node.attributes or {}
        if str(attrs.get("decision_mode", "")).lower() != "llm":
            return CommandResult.error_result("aico requires decision_mode=llm on the agent node")
        res = run_npc_agent_nlp_tick(context.db_session, node, context, message)
        context.db_session.commit()
        sid = str(attrs.get("service_id") or "aico")
        return assistant_nlp_command_result("aico", res, service_id=sid)


class AgentCommand(SystemCommand):
    """
    List visible agents and their status, or query one agent by service id.
    """

    def __init__(self):
        super().__init__(
            "agent",
            (
                "Inspect and drive agents. Subcommands: `agent list` "
                "(all registered agents), `agent status <id>` (one "
                "agent's runtime status), `agent nlp <handle> <text>` "
                "(drive an assistant's NLP pipeline with a prompt). "
                "Prefer `agent_capabilities <service_id>` when you only "
                "need the capability summary."
            ),
            [],
        )

    def get_usage(self) -> str:
        return "agent <list|status> ..."

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        from app.commands.i18n.locale_text import resolve_locale

        locale = resolve_locale(context)
        if not context.db_session:
            return CommandResult.error_result(
                _agent_list_text(
                    locale,
                    "error.no_session",
                    "database session required",
                )
            )
        if not args:
            return CommandResult.error_result(self.get_usage(), is_usage=True)
        sub = str(args[0]).lower().strip()
        session = context.db_session
        if sub == "list":
            rows = []
            for node in _query_active_npc_agent_nodes(session):
                rows.append(_agent_row_dict(node, session))
            rows.sort(key=lambda r: (r.get("service_id") or "", r.get("name") or ""))
            message = _format_agent_list_message(rows, locale)
            return CommandResult.success_result(
                message,
                data={"agents": rows, "total": len(rows)},
            )
        if sub == "status":
            if len(args) < 2:
                return CommandResult.error_result("usage: agent status <service_id>")
            handle = args[1].strip()
            matches = _find_npc_agent_nodes_by_handle(session, handle)
            if len(matches) != 1:
                return CommandResult.error_result(AGENT_STATUS_ACCESS_ERROR)
            return CommandResult.success_result(
                json.dumps(_agent_row_dict(matches[0], session), ensure_ascii=False)
            )
        return CommandResult.error_result(self.get_usage(), is_usage=True)


_agent_commands_cache = None
_agent_commands_lock = threading.Lock()


def get_agent_commands() -> List[SystemCommand]:
    """Factory + cache to avoid module-import time command object construction side effects."""
    global _agent_commands_cache
    if _agent_commands_cache is not None:
        return _agent_commands_cache
    with _agent_commands_lock:
        if _agent_commands_cache is None:
            _agent_commands_cache = [
                AgentCapabilitiesCommand(),
                AgentToolsCommand(),
                AicoCommand(),
                AgentCommand(),
            ]
    return _agent_commands_cache
