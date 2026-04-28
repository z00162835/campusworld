"""``task pool`` admin command (Phase B).

Subcommands:
  task pool list    — list active (and optionally inactive) pools.
  task pool show    — show one pool by key.
  task pool create  — admin: insert new pool.
  task pool update  — admin: update mutable fields.
  task pool disable — admin: set is_active=false.
  task pool enable  — admin: set is_active=true.

Pool admin operations write directly to ``task_pools`` (not protected by
the I3 single-write-path guard, which only covers state-machine ledgers).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.commands.base import AdminCommand, CommandContext, CommandResult
from app.core.database import db_session_context
from app.services.task.permissions import TASK_POOL_ADMIN, TASK_READ
from app.services.task.task_pool_service import get_pool_by_key, list_pools
from app.services.task.visibility import (
    PHASE_B_SUPPORTED_VISIBILITIES,
    is_phase_b_supported,
)

from ._helpers import (
    i18n,
    parse_argv,
    require_permission,
    usage_result,
)


logger = logging.getLogger(__name__)


_LIST_BOOL_FLAGS = {"include-inactive"}


_SUB_PERMS = {
    "list": TASK_READ,
    "show": TASK_READ,
    "create": TASK_POOL_ADMIN,
    "update": TASK_POOL_ADMIN,
    "disable": TASK_POOL_ADMIN,
    "enable": TASK_POOL_ADMIN,
}


_DEFAULT_POOL_PUBLISH_ACL: Dict[str, Any] = {
    "_schema_version": 1,
    "principal_kinds": ["user", "agent", "system"],
    "default": "allow",
}

_DEFAULT_POOL_CONSUME_ACL: Dict[str, Any] = {
    "_schema_version": 1,
    "principal_kinds": ["user", "agent"],
    "default": "allow",
}


class TaskPoolCommand(AdminCommand):
    """``task pool`` family — registry CRUD + read."""

    def __init__(self) -> None:
        super().__init__(
            name="task.pool",
            description="Task pool admin/read commands (list / show / create / update / disable / enable)",
            aliases=[],
        )

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return usage_result(
                context,
                "usage.pool",
                "task pool <list|show|create|update|disable|enable> [args]",
            )
        sub = str(args[0]).lower()
        rest = args[1:]
        handler = {
            "list": self._do_list,
            "show": self._do_show,
            "create": self._do_create,
            "update": self._do_update,
            "disable": self._do_disable,
            "enable": self._do_enable,
        }.get(sub)
        if handler is None:
            return CommandResult.error_result(
                f"unknown pool subcommand: {sub}",
                error="commands.task.error.invalid_event",
            )
        gate = require_permission(context, _SUB_PERMS[sub])
        if gate is not None:
            return gate
        return handler(context, rest)

    def _usage_unknown_bool(
        self,
        ctx: CommandContext,
        parsed,
        *,
        allowed: set[str],
        usage_key: str,
        usage_default: str,
    ) -> Optional[CommandResult]:
        if set(parsed.bools).issubset(allowed):
            return None
        return usage_result(ctx, usage_key, usage_default)

    # ------------------------------------------------------------------
    def _do_list(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        parsed = parse_argv(args, bool_flags=_LIST_BOOL_FLAGS)
        bad = self._usage_unknown_bool(
            ctx,
            parsed,
            allowed=_LIST_BOOL_FLAGS,
            usage_key="usage.pool_list",
            usage_default="task pool list [--scope <prefix>] [--include-inactive]",
        )
        if bad is not None:
            return bad
        scope = parsed.flags.get("scope")
        with db_session_context() as session:
            pools = list_pools(
                session,
                include_inactive="include-inactive" in parsed.bools,
                key_prefix=scope,
                limit=int(parsed.flags.get("limit", "100")),
                offset=int(parsed.flags.get("offset", "0")),
            )
        if not pools:
            return CommandResult.success_result(
                i18n(ctx, "pool.list.empty", default="No active pools."),
                data={"items": [], "total": 0},
            )
        header = i18n(ctx, "pool.list.header", default=f"Pools (total={len(pools)})", total=len(pools))
        row_tmpl = i18n(
            ctx, "pool.list.row",
            default="{key}  active={is_active}  visibility={visibility}  priority={priority}  workflow={workflow}",
        )
        lines = [header]
        for p in pools:
            lines.append(
                row_tmpl.format(
                    key=p["key"],
                    is_active=p["is_active"],
                    visibility=p["default_visibility"],
                    priority=p["default_priority"],
                    workflow=f"{(p['default_workflow_ref'] or {}).get('key', '?')}:{(p['default_workflow_ref'] or {}).get('version', '?')}",
                )
            )
        return CommandResult.success_result(
            "\n".join(lines),
            data={"items": pools, "total": len(pools)},
        )

    def _do_show(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return usage_result(ctx, "usage.pool_show", "task pool show <key>")
        key = args[0]
        with db_session_context() as session:
            pool = get_pool_by_key(session, key)
        if pool is None:
            return CommandResult.error_result(
                i18n(ctx, "error.pool_not_found", default=f"pool {key} not found", detail=key),
                error="commands.task.error.pool_not_found",
            )
        title = i18n(ctx, "pool.show.title", default=f"Task pool {key}", key=key)
        lines = [
            title,
            f"  id              : {pool['id']}",
            f"  display_name    : {pool['display_name']}",
            f"  is_active       : {pool['is_active']}",
            f"  default_workflow: {pool['default_workflow_ref']}",
            f"  default_visibility: {pool['default_visibility']}",
            f"  default_priority: {pool['default_priority']}",
            f"  publish_acl     : {pool['publish_acl']}",
            f"  consume_acl     : {pool['consume_acl']}",
        ]
        return CommandResult.success_result("\n".join(lines), data=pool)

    # ------------------------------------------------------------------
    def _do_create(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        parsed = parse_argv(args, bool_flags=set())
        bad = self._usage_unknown_bool(
            ctx,
            parsed,
            allowed=set(),
            usage_key="usage.pool_create",
            usage_default="task pool create <key> --display-name <N>",
        )
        if bad is not None:
            return bad
        if not parsed.positional:
            return usage_result(
                ctx, "usage.pool_create",
                "task pool create <key> --display-name <N>",
            )
        key = parsed.positional[0]
        display_name = parsed.flags.get("display-name")
        if not display_name:
            return usage_result(
                ctx, "usage.pool_create",
                "task pool create <key> --display-name <N>",
            )
        workflow_spec = parsed.flags.get("workflow", "default_v1:1")
        try:
            wf_key, wf_ver = workflow_spec.split(":", 1)
            wf_version = int(wf_ver)
        except (ValueError, AttributeError):
            return usage_result(
                ctx, "usage.pool_create",
                "task pool create <key> --display-name <N> [--workflow default_v1:1]",
            )
        visibility = parsed.flags.get("visibility", "pool_open")
        if not is_phase_b_supported(visibility):
            return CommandResult.error_result(
                i18n(
                    ctx,
                    "error.visibility_unsupported",
                    default=(
                        f"visibility={visibility!r} is not supported "
                        f"(allowed: {sorted(PHASE_B_SUPPORTED_VISIBILITIES)})"
                    ),
                    detail=visibility,
                ),
                error="commands.task.error.visibility_unsupported",
            )
        priority = parsed.flags.get("priority", "normal")
        description = parsed.flags.get("description")

        params = {
            "key": key,
            "display_name": display_name,
            "description": description,
            "default_workflow_ref": json.dumps(
                {"_schema_version": 1, "key": wf_key, "version": wf_version},
                ensure_ascii=False,
            ),
            "default_visibility": visibility,
            "default_priority": priority,
            "publish_acl": json.dumps(_DEFAULT_POOL_PUBLISH_ACL, ensure_ascii=False),
            "consume_acl": json.dumps(_DEFAULT_POOL_CONSUME_ACL, ensure_ascii=False),
            "attributes": json.dumps({"_schema_version": 1}, ensure_ascii=False),
        }
        try:
            with db_session_context() as session:
                row = session.execute(
                    text(
                        """
                        INSERT INTO task_pools (
                            key, display_name, description,
                            owner_principal_id, owner_principal_kind,
                            default_workflow_ref, default_visibility, default_priority,
                            publish_acl, consume_acl, quota, attributes, is_active
                        ) VALUES (
                            :key, :display_name, :description,
                            NULL, NULL,
                            CAST(:default_workflow_ref AS jsonb), :default_visibility, :default_priority,
                            CAST(:publish_acl AS jsonb), CAST(:consume_acl AS jsonb),
                            NULL, CAST(:attributes AS jsonb), TRUE
                        )
                        RETURNING id
                        """
                    ),
                    params,
                ).first()
                session.commit()
                pool_id = int(row[0])
        except Exception as exc:  # pragma: no cover - DB-specific path
            logger.error("task pool create failed: %s", exc, exc_info=True)
            return CommandResult.error_result(
                f"task pool create failed: {exc}",
                error="commands.task.error.generic",
            )
        return CommandResult.success_result(
            i18n(ctx, "pool.create.success", default=f"pool {key} created", key=key, id=pool_id),
            data={"key": key, "id": pool_id},
        )

    def _do_update(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        parsed = parse_argv(args, bool_flags=set())
        bad = self._usage_unknown_bool(
            ctx,
            parsed,
            allowed=set(),
            usage_key="usage.pool_update",
            usage_default="task pool update <key> [--display-name N]",
        )
        if bad is not None:
            return bad
        if not parsed.positional:
            return usage_result(ctx, "usage.pool_update", "task pool update <key> [--display-name N]")
        key = parsed.positional[0]
        if "visibility" in parsed.flags and not is_phase_b_supported(parsed.flags["visibility"]):
            return CommandResult.error_result(
                i18n(
                    ctx,
                    "error.visibility_unsupported",
                    default=(
                        f"visibility={parsed.flags['visibility']!r} is not supported "
                        f"(allowed: {sorted(PHASE_B_SUPPORTED_VISIBILITIES)})"
                    ),
                    detail=parsed.flags["visibility"],
                ),
                error="commands.task.error.visibility_unsupported",
            )
        sets: List[str] = []
        params: Dict[str, Any] = {"key": key}
        for cli_flag, sql_col in (
            ("display-name", "display_name"),
            ("description", "description"),
            ("visibility", "default_visibility"),
            ("priority", "default_priority"),
        ):
            if cli_flag in parsed.flags:
                sets.append(f"{sql_col} = :{sql_col}")
                params[sql_col] = parsed.flags[cli_flag]
        if not sets:
            return usage_result(ctx, "usage.pool_update", "task pool update <key> [--display-name N]")
        sql = f"UPDATE task_pools SET {', '.join(sets)}, updated_at = now() WHERE key = :key RETURNING id"
        with db_session_context() as session:
            row = session.execute(text(sql), params).first()
            session.commit()
        if row is None:
            return CommandResult.error_result(
                i18n(ctx, "error.pool_not_found", default=f"pool {key} not found", detail=key),
                error="commands.task.error.pool_not_found",
            )
        return CommandResult.success_result(
            i18n(ctx, "pool.update.success", default=f"pool {key} updated", key=key),
            data={"key": key, "id": int(row[0])},
        )

    def _do_disable(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        return self._set_active(ctx, args, is_active=False, message_key="pool.disable.success",
                                 default_msg="pool disabled")

    def _do_enable(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        return self._set_active(ctx, args, is_active=True, message_key="pool.enable.success",
                                 default_msg="pool enabled")

    def _set_active(
        self,
        ctx: CommandContext,
        args: List[str],
        *,
        is_active: bool,
        message_key: str,
        default_msg: str,
    ) -> CommandResult:
        if not args:
            verb = "enable" if is_active else "disable"
            return usage_result(ctx, f"usage.pool_{verb}", f"task pool {verb} <key>")
        key = args[0]
        with db_session_context() as session:
            row = session.execute(
                text(
                    "UPDATE task_pools SET is_active = :ia, updated_at = now() WHERE key = :k RETURNING id"
                ),
                {"ia": is_active, "k": key},
            ).first()
            session.commit()
        if row is None:
            return CommandResult.error_result(
                i18n(ctx, "error.pool_not_found", default=f"pool {key} not found", detail=key),
                error="commands.task.error.pool_not_found",
            )
        return CommandResult.success_result(
            i18n(ctx, message_key, default=f"{default_msg}: {key}", key=key),
            data={"key": key, "is_active": is_active},
        )


_POOL_HANDLER = TaskPoolCommand()


def execute_task_pool_command(ctx: CommandContext, args: List[str]) -> CommandResult:
    """Execute `task pool ...` via a shared internal handler."""
    return _POOL_HANDLER.execute(ctx, args)
