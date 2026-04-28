"""``task`` command — top-level dispatcher for the Phase B task family.

Subcommands:
  task create   — create + initial assignment + outbox
  task list     — visibility-filtered listing
  task show     — single task detail
  task claim    — state machine event=claim
  task assign   — state machine event=assign
  task publish  — state machine event=publish
  task complete — state machine event=complete

SSOT: ``docs/command/SPEC/features/CMD_task.md``.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.commands.base import CommandContext, CommandResult, GameCommand
from app.core.database import db_session_context
from app.services.task.acl import evaluate_acl
from app.services.task.errors import PublishAclDenied, TaskSystemError
from app.services.task.permissions import (
    TASK_ASSIGN,
    TASK_CLAIM,
    TASK_CREATE,
    TASK_PUBLISH,
    TASK_READ,
    TASK_UPDATE,
)
from app.services.task.task_state_machine import (
    TransitionResult,
    create_task,
    transition,
)
from app.services.task.visibility import (
    PHASE_B_SUPPORTED_VISIBILITIES,
    is_phase_b_supported,
)

from ._helpers import (
    correlation_id_from_context,
    derive_idempotency_key,
    i18n,
    parse_argv,
    require_permission,
    resolve_principal_or_error,
    task_error_to_result,
    trace_id_from_context,
    usage_result,
)
from .task_pool_command import execute_task_pool_command


logger = logging.getLogger(__name__)


_SUB_PERM = {
    "create": TASK_CREATE,
    "list": TASK_READ,
    "show": TASK_READ,
    "claim": TASK_CLAIM,
    "assign": TASK_ASSIGN,
    "publish": TASK_PUBLISH,
    "complete": TASK_UPDATE,
}


_CREATE_BOOL_FLAGS = {"draft"}
_LIST_BOOL_FLAGS = {"mine", "assigned"}
_TRANSITION_BOOL_FLAGS: set[str] = set()
_TASK_LIST_MAX_LIMIT = max(1, int(os.getenv("TASK_LIST_MAX_LIMIT", "200")))


class TaskCommand(GameCommand):
    """Phase B implementation of the ``task`` command family."""

    def __init__(self) -> None:
        super().__init__(
            name="task",
            description="Task command family (create / list / show / claim / assign / publish / complete)",
            aliases=["tasks"],
            game_name="campusworld",
        )

    # ------------------------------------------------------------------
    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return usage_result(
                context,
                "usage.root",
                "task <create|list|show|claim|assign|publish|complete> [...]",
            )
        sub = str(args[0]).lower()
        rest = args[1:]
        if sub == "pool":
            return self._do_pool(context, rest)
        handler = {
            "create": self._do_create,
            "list": self._do_list,
            "show": self._do_show,
            "claim": self._do_claim,
            "assign": self._do_assign,
            "publish": self._do_publish,
            "complete": self._do_complete,
        }.get(sub)
        if handler is None:
            return CommandResult.error_result(
                i18n(
                    context,
                    "error.invalid_event",
                    default=f"unknown subcommand: {sub}",
                    detail=sub,
                ),
                error="commands.task.error.invalid_event",
            )
        gate = require_permission(context, _SUB_PERM[sub])
        if gate is not None:
            return gate
        return handler(context, rest)

    # ------------------------------------------------------------------
    # Write subcommands
    # ------------------------------------------------------------------

    def _do_pool(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        return execute_task_pool_command(ctx, args)

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

    def _do_create(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        parsed = parse_argv(args, bool_flags=_CREATE_BOOL_FLAGS)
        bad = self._usage_unknown_bool(
            ctx,
            parsed,
            allowed=_CREATE_BOOL_FLAGS,
            usage_key="usage.create",
            usage_default="task create --title <T> ...",
        )
        if bad is not None:
            return bad
        title = parsed.flags.get("title")
        if not title:
            return usage_result(ctx, "usage.create", "task create --title <T> ...")

        actor, err = resolve_principal_or_error(ctx)
        if err is not None:
            return err
        idem = parsed.flags.get("idempotency-key") or derive_idempotency_key(
            actor=actor,
            command_name="task.create",
            args=args,
            correlation_id=correlation_id_from_context(ctx),
        )

        pool_id: Optional[int] = None
        pool_default_workflow_key: Optional[str] = None
        pool_default_visibility: Optional[str] = None
        pool_default_priority: Optional[str] = None
        pool_key = parsed.flags.get("to-pool")
        if pool_key:
            with db_session_context() as session:
                row = session.execute(
                    text(
                        """
                        SELECT id, is_active, publish_acl,
                               default_workflow_ref, default_visibility, default_priority
                          FROM task_pools
                         WHERE key = :k
                        """
                    ),
                    {"k": pool_key},
                ).first()
                if row is None:
                    return CommandResult.error_result(
                        i18n(
                            ctx,
                            "error.pool_not_found",
                            default=f"pool {pool_key} not found",
                            detail=pool_key,
                        ),
                        error="commands.task.error.pool_not_found",
                    )
                pool_id = int(row[0])
                pool_active = bool(row[1])
                pool_publish_acl = self._decode_jsonb(row[2])
                pool_workflow_ref = self._decode_jsonb(row[3])
                pool_default_visibility = row[4]
                pool_default_priority = row[5]
                pool_default_workflow_key = (
                    pool_workflow_ref.get("key")
                    if isinstance(pool_workflow_ref, dict)
                    else None
                )
                if not pool_active:
                    return CommandResult.error_result(
                        i18n(
                            ctx,
                            "error.pool_inactive",
                            default=f"pool {pool_key} is inactive",
                            detail=pool_key,
                        ),
                        error="commands.task.error.pool_inactive",
                    )
                decision = evaluate_acl(actor, pool_publish_acl)
                if not decision.allow:
                    return task_error_to_result(
                        ctx,
                        PublishAclDenied(
                            f"publish_acl denied for pool={pool_key}: {decision.reason}"
                        ),
                    )

        workflow_flag = parsed.flags.get("workflow")
        workflow_key = (
            workflow_flag.split(":", 1)[0]
            if workflow_flag
            else (pool_default_workflow_key or "default_v1")
        )
        priority = parsed.flags.get("priority", pool_default_priority or "normal")
        visibility = parsed.flags.get("visibility", pool_default_visibility or "private")

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

        # D3.1: `--draft` keeps the task in `draft` state even when --to-pool
        # is provided. Without --draft, --to-pool implies an atomic create+publish.
        keep_draft = "draft" in parsed.bools

        correlation_id = correlation_id_from_context(ctx)
        trace_id = trace_id_from_context(ctx)

        try:
            with db_session_context() as session:
                with session.begin():
                    # `create --to-pool` is implemented as an atomic create+publish
                    # sequence inside one outer DB transaction (unless --draft).
                    created = create_task(
                        title=title,
                        actor=actor,
                        workflow_key=workflow_key,
                        pool_id=pool_id,
                        priority=priority,
                        visibility=visibility,
                        assignee_kind="pool" if pool_id else parsed.flags.get("assignee-kind", "user"),
                        correlation_id=correlation_id,
                        trace_id=trace_id,
                        idempotency_key=idem,
                        db_session=session,
                    )
                    if pool_id is None or keep_draft:
                        res = created
                    else:
                        res = transition(
                            task_id=created.task_id,
                            event="publish",
                            actor_principal=actor,
                            expected_version=created.state_version,
                            idempotency_key=f"{idem}:publish",
                            correlation_id=correlation_id,
                            trace_id=trace_id,
                            payload={"pool_id": pool_id},
                            db_session=session,
                        )
        except TaskSystemError as exc:
            return task_error_to_result(ctx, exc)
        return self._success(
            ctx, "create", res, extra={"pool_key": pool_key, "kept_draft": keep_draft}
        )

    def _do_claim(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        return self._dispatch_event(ctx, args, event="claim", usage_key="usage.claim",
                                     usage_default="task claim <id>")

    def _do_complete(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        return self._dispatch_event(ctx, args, event="complete", usage_key="usage.complete",
                                     usage_default="task complete <id>")

    def _do_assign(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        parsed = parse_argv(args, bool_flags=_TRANSITION_BOOL_FLAGS)
        bad = self._usage_unknown_bool(
            ctx,
            parsed,
            allowed=_TRANSITION_BOOL_FLAGS,
            usage_key="usage.assign",
            usage_default="task assign <id> --to <principal_id> [--kind ...]",
        )
        if bad is not None:
            return bad
        if not parsed.positional:
            return usage_result(ctx, "usage.assign", "task assign <id> --to <principal_id> [--kind ...]")
        try:
            task_id = int(parsed.positional[0])
        except (TypeError, ValueError):
            return usage_result(ctx, "usage.assign", "task assign <id> --to <principal_id>")
        target_id_raw = parsed.flags.get("to")
        if target_id_raw is None:
            return usage_result(ctx, "usage.assign", "task assign <id> --to <principal_id>")
        target_kind = parsed.flags.get("kind", "user")
        payload: Dict[str, Any] = {"principal_kind": target_kind}
        if target_kind == "group":
            payload["principal_tag"] = target_id_raw
        else:
            try:
                payload["principal_id"] = int(target_id_raw)
            except (TypeError, ValueError):
                return usage_result(ctx, "usage.assign", "task assign <id> --to <principal_id>")
        return self._run_transition(
            ctx, task_id=task_id, event="assign", parsed=parsed, payload=payload,
            sub_args=args,
        )

    def _do_publish(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        parsed = parse_argv(args, bool_flags=_TRANSITION_BOOL_FLAGS)
        bad = self._usage_unknown_bool(
            ctx,
            parsed,
            allowed=_TRANSITION_BOOL_FLAGS,
            usage_key="usage.publish",
            usage_default="task publish <id> --to-pool <key>",
        )
        if bad is not None:
            return bad
        if not parsed.positional:
            return usage_result(ctx, "usage.publish", "task publish <id> --to-pool <key>")
        try:
            task_id = int(parsed.positional[0])
        except (TypeError, ValueError):
            return usage_result(ctx, "usage.publish", "task publish <id> --to-pool <key>")
        pool_key = parsed.flags.get("to-pool")
        if not pool_key:
            return usage_result(ctx, "usage.publish", "task publish <id> --to-pool <key>")
        return self._run_transition(
            ctx,
            task_id=task_id,
            event="publish",
            parsed=parsed,
            payload={"pool_key": pool_key},
            sub_args=args,
        )

    # ------------------------------------------------------------------
    # Read subcommands
    # ------------------------------------------------------------------

    def _do_list(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        parsed = parse_argv(args, bool_flags=_LIST_BOOL_FLAGS)
        bad = self._usage_unknown_bool(
            ctx,
            parsed,
            allowed=_LIST_BOOL_FLAGS,
            usage_key="usage.list",
            usage_default="task list [--limit N] [--offset O]",
        )
        if bad is not None:
            return bad
        actor, err = resolve_principal_or_error(ctx)
        if err is not None:
            return err
        try:
            limit = int(parsed.flags.get("limit", "20"))
            offset = int(parsed.flags.get("offset", "0"))
        except ValueError:
            return usage_result(ctx, "usage.list", "task list [--limit N] [--offset O]")
        # Defensive caps: malicious / accidental large LIMIT must not fan out.
        limit = max(1, min(limit, _TASK_LIST_MAX_LIMIT))
        offset = max(0, offset)
        pool_key = parsed.flags.get("pool")

        with db_session_context() as session:
            # D1.1: pre-evaluate pool consume_acl in Python over the small
            # active-pool cardinality (typically <100); push the resulting
            # allowed pool ids into the SQL predicate. Sentinel `[0]` so
            # `= ANY(...)` always has a valid bigint[] literal (0 is never a
            # real BIGSERIAL pool id).
            visible_pool_ids = self._compute_visible_pool_ids(session, actor)
            params: Dict[str, Any] = {
                "pid": actor.id,
                "pkind": actor.kind,
                "visible_pool_ids": visible_pool_ids or [0],
                "limit": limit,
                "offset": offset,
            }

            visibility_predicate = """
              (
                EXISTS (
                    SELECT 1 FROM task_assignments a
                     WHERE a.task_node_id = n.id
                       AND a.is_active
                       AND a.principal_id = :pid
                       AND a.principal_kind = :pkind
                )
                OR (
                    n.attributes->>'visibility' = 'explicit'
                    AND EXISTS (
                        SELECT 1 FROM task_assignments a
                         WHERE a.task_node_id = n.id
                           AND a.principal_id = :pid
                           AND a.principal_kind = :pkind
                    )
                )
                OR (
                    n.attributes->>'visibility' = 'pool_open'
                    AND n.attributes->>'assignee_kind' = 'pool'
                    AND n.attributes->>'current_state' IN ('open', 'rejected')
                    AND (n.attributes->>'pool_id')::bigint = ANY(:visible_pool_ids)
                )
              )
            """

            narrow_clause = ""
            if "mine" in parsed.bools:
                narrow_clause = (
                    " AND EXISTS (SELECT 1 FROM task_assignments a"
                    "  WHERE a.task_node_id = n.id AND a.is_active"
                    "    AND a.principal_id = :pid AND a.principal_kind = :pkind)"
                )
            elif "assigned" in parsed.bools:
                narrow_clause = (
                    " AND EXISTS (SELECT 1 FROM task_assignments a"
                    "  WHERE a.task_node_id = n.id AND a.is_active"
                    "    AND a.role = 'executor'"
                    "    AND a.principal_id = :pid AND a.principal_kind = :pkind)"
                )

            pool_clause = ""
            if pool_key:
                pool_clause = " AND p.key = :pool_key"
                params["pool_key"] = pool_key

            sql = f"""
                SELECT n.id,
                       n.attributes->>'current_state' AS state,
                       n.attributes->>'title' AS title,
                       n.attributes->>'priority' AS priority,
                       p.key AS pool_key,
                       COUNT(*) OVER () AS total_count
                  FROM nodes n
             LEFT JOIN task_pools p ON p.id = (n.attributes->>'pool_id')::bigint
                 WHERE n.type_code = 'task'
                   AND n.is_active = TRUE
                   AND {visibility_predicate}
                   {narrow_clause}
                   {pool_clause}
              ORDER BY n.created_at DESC
                 LIMIT :limit OFFSET :offset
            """
            rows = session.execute(text(sql), params).all()

        # D1.2: total is the global match count (COUNT(*) OVER ()), not the
        # current page size; clients can rely on this for pagination UX.
        total = int(rows[0].total_count) if rows else 0
        items = [
            {
                "id": int(r.id),
                "state": r.state,
                "title": r.title,
                "priority": r.priority,
                "pool_key": r.pool_key,
            }
            for r in rows
        ]
        end = offset + len(items)
        if not items:
            msg = i18n(ctx, "list.empty", default="No tasks match.")
        else:
            header = i18n(
                ctx, "list.header",
                default=f"Tasks (total={total})",
                total=total, offset=offset, end=end,
            )
            row_tmpl = i18n(
                ctx, "list.row",
                default="#{id}  state={state}  pool={pool_key}  priority={priority}  title={title}",
            )
            lines = [header]
            for it in items:
                lines.append(
                    row_tmpl.format(
                        id=it["id"], state=it["state"] or "-",
                        pool_key=it["pool_key"] or "-",
                        priority=it["priority"] or "-",
                        title=it["title"] or "-",
                    )
                )
            msg = "\n".join(lines)
        return CommandResult.success_result(msg, data={"items": items, "total": total})

    def _do_show(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return usage_result(ctx, "usage.show", "task show <id>")
        try:
            task_id = int(args[0])
        except (TypeError, ValueError):
            return usage_result(ctx, "usage.show", "task show <id>")
        actor, err = resolve_principal_or_error(ctx)
        if err is not None:
            return err
        with db_session_context() as session:
            row = session.execute(
                text(
                    """
                    SELECT n.id, n.name, n.created_at, n.attributes,
                           p.key AS pool_key,
                           p.is_active AS pool_is_active,
                           p.consume_acl AS pool_consume_acl,
                           EXISTS (
                                SELECT 1 FROM task_assignments a
                                 WHERE a.task_node_id = n.id
                                   AND a.is_active
                                   AND a.principal_id = :pid
                                   AND a.principal_kind = :pkind
                           ) AS has_active_assignment,
                           EXISTS (
                                SELECT 1 FROM task_assignments a
                                 WHERE a.task_node_id = n.id
                                   AND a.principal_id = :pid
                                   AND a.principal_kind = :pkind
                           ) AS has_any_assignment
                      FROM nodes n
                 LEFT JOIN task_pools p ON p.id = (n.attributes->>'pool_id')::bigint
                     WHERE n.id = :id
                       AND n.type_code = 'task'
                       AND n.is_active = TRUE
                    """
                ),
                {"id": task_id, "pid": actor.id, "pkind": actor.kind},
            ).first()
            if row is None:
                return CommandResult.error_result(
                    i18n(ctx, "error.not_found", default=f"task {task_id} not found", task_id=task_id),
                    error="commands.task.error.not_found",
                )
            attrs = row.attributes if isinstance(row.attributes, dict) else json.loads(row.attributes or "{}")
            if not self._can_view_task_row(
                actor=actor,
                row=row,
                attrs=attrs,
                session=session,
            ):
                # Existence hardening: for callers without visibility we return
                # not_found (same shape as missing/soft-deleted task) so task id
                # probing cannot distinguish "exists but forbidden".
                return CommandResult.error_result(
                    i18n(
                        ctx,
                        "error.not_found",
                        default=f"task {task_id} not found",
                        task_id=task_id,
                    ),
                    error="commands.task.error.not_found",
                )
            recent = session.execute(
                text(
                    """
                    SELECT event_seq, event, from_state, to_state, created_at
                      FROM task_state_transitions
                     WHERE task_node_id = :id
                     ORDER BY event_seq DESC LIMIT 10
                    """
                ),
                {"id": task_id},
            ).all()
            assignments = session.execute(
                text(
                    """
                    SELECT principal_id, principal_kind, principal_tag, role, stage, is_active
                      FROM task_assignments
                     WHERE task_node_id = :id AND is_active = TRUE
                    """
                ),
                {"id": task_id},
            ).all()

        title_line = i18n(ctx, "show.title", default=f"Task #{task_id}", id=task_id)
        lines = [
            title_line,
            f"  state          : {attrs.get('current_state')}",
            f"  state_version  : {attrs.get('state_version')}",
            f"  workflow_ref   : {attrs.get('workflow_ref')}",
            f"  pool           : {row.pool_key or '-'}",
            f"  priority       : {attrs.get('priority')}",
            f"  visibility     : {attrs.get('visibility')}",
            f"  title          : {row.name}",
            f"  active assigns : {len(assignments)}",
            "  recent events  :",
        ]
        for ev in recent:
            lines.append(f"    seq={ev.event_seq} {ev.event} {ev.from_state}→{ev.to_state} at={ev.created_at}")

        safe_attrs = {
            "current_state": attrs.get("current_state"),
            "state_version": attrs.get("state_version"),
            "workflow_ref": attrs.get("workflow_ref"),
            "title": attrs.get("title"),
            "priority": attrs.get("priority"),
            "visibility": attrs.get("visibility"),
            "pool_id": attrs.get("pool_id"),
            "due_at": attrs.get("due_at"),
            "assignee_kind": attrs.get("assignee_kind"),
        }

        data = {
            "id": int(row.id),
            "name": row.name,
            "attributes": safe_attrs,
            "pool_key": row.pool_key,
            "active_assignments": [
                {
                    "principal_id": a.principal_id,
                    "principal_kind": a.principal_kind,
                    "principal_tag": a.principal_tag,
                    "role": a.role,
                    "stage": a.stage,
                }
                for a in assignments
            ],
            "recent_transitions": [
                {
                    "event_seq": int(t.event_seq),
                    "event": t.event,
                    "from_state": t.from_state,
                    "to_state": t.to_state,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in recent
            ],
        }
        return CommandResult.success_result("\n".join(lines), data=data)

    @staticmethod
    def _decode_jsonb(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str):
            try:
                loaded = json.loads(value)
                if isinstance(loaded, dict):
                    return loaded
            except ValueError:
                return {}
        return {}

    def _compute_visible_pool_ids(self, session, actor) -> List[int]:
        """Return ids of active pools whose ``consume_acl`` allows ``actor``.

        Cardinality of pools is small (~tens) compared to tasks (~millions);
        evaluating ACL once per pool here lets the task list query push
        ``pool_id = ANY(:visible_pool_ids)`` to SQL and benefit from the
        ``ix_task_nodes_pool_id`` JSONB expression index.
        """
        rows = session.execute(
            text(
                """
                SELECT id, consume_acl
                  FROM task_pools
                 WHERE is_active = TRUE
                """
            )
        ).all()
        out: List[int] = []
        for r in rows:
            acl = self._decode_jsonb(r.consume_acl)
            if evaluate_acl(actor, acl).allow:
                out.append(int(r.id))
        return out

    def _can_view_pool_open_row(self, actor, row) -> bool:
        if str(row.assignee_kind or "") != "pool":
            return False
        if str(row.visibility or "") != "pool_open":
            return False
        if str(row.state or "") not in {"open", "rejected"}:
            return False
        if not bool(row.pool_is_active):
            return False
        acl = self._decode_jsonb(row.pool_consume_acl)
        return evaluate_acl(actor, acl).allow

    def _can_view_task_row(
        self,
        *,
        actor,
        row,
        attrs: Dict[str, Any],
        session,
    ) -> bool:
        """Apply the Phase B visibility matrix on a single row (used by show).

        D2.3 / D4.1: ``role_scope`` and ``world_scope`` are deferred to Phase C
        (need F11 data_access predicate). For show we deny silently — task
        existence is already gated by the row lookup, so leaking
        "supports phase-B-only" here would only narrow the deny reason, not
        broaden access. Write paths reject these visibility kinds explicitly
        with ``error.visibility_unsupported``.
        """
        if bool(row.has_active_assignment):
            return True
        visibility = str(attrs.get("visibility") or "private")
        if visibility == "explicit" and bool(row.has_any_assignment):
            return True
        if visibility == "pool_open":
            return self._can_view_pool_open_row(actor, row)
        # role_scope / world_scope / unknown → deny (Phase B contract).
        return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _dispatch_event(
        self,
        ctx: CommandContext,
        args: List[str],
        *,
        event: str,
        usage_key: str,
        usage_default: str,
    ) -> CommandResult:
        parsed = parse_argv(args, bool_flags=_TRANSITION_BOOL_FLAGS)
        bad = self._usage_unknown_bool(
            ctx,
            parsed,
            allowed=_TRANSITION_BOOL_FLAGS,
            usage_key=usage_key,
            usage_default=usage_default,
        )
        if bad is not None:
            return bad
        if not parsed.positional:
            return usage_result(ctx, usage_key, usage_default)
        try:
            task_id = int(parsed.positional[0])
        except (TypeError, ValueError):
            return usage_result(ctx, usage_key, usage_default)
        return self._run_transition(
            ctx, task_id=task_id, event=event, parsed=parsed, payload={}, sub_args=args
        )

    def _run_transition(
        self,
        ctx: CommandContext,
        *,
        task_id: int,
        event: str,
        parsed,
        payload: Dict[str, Any],
        sub_args: List[str],
    ) -> CommandResult:
        actor, err = resolve_principal_or_error(ctx)
        if err is not None:
            return err
        idem = parsed.flags.get("idempotency-key") or derive_idempotency_key(
            actor=actor,
            command_name=f"task.{event}",
            args=sub_args,
            correlation_id=correlation_id_from_context(ctx),
        )
        # Snapshot expected_version.
        with db_session_context() as session:
            row = session.execute(
                text("SELECT (attributes->>'state_version')::int FROM nodes WHERE id = :id AND type_code='task'"),
                {"id": task_id},
            ).first()
            if row is None:
                return CommandResult.error_result(
                    i18n(ctx, "error.not_found", default=f"task {task_id} not found", task_id=task_id),
                    error="commands.task.error.not_found",
                )
            expected_version = int(row[0] or 0)

        try:
            res = transition(
                task_id=task_id,
                event=event,
                actor_principal=actor,
                expected_version=expected_version,
                idempotency_key=idem,
                correlation_id=correlation_id_from_context(ctx),
                trace_id=trace_id_from_context(ctx),
                payload=payload,
            )
        except TaskSystemError as exc:
            return task_error_to_result(ctx, exc)
        return self._success(
            ctx,
            event,
            res,
            extra={"pool_key": payload.get("pool_key") if event == "publish" else None},
        )

    def _success(
        self,
        ctx: CommandContext,
        event: str,
        res: TransitionResult,
        *,
        extra: Optional[Dict[str, Any]] = None,
    ) -> CommandResult:
        extra = extra or {}
        msg = i18n(
            ctx,
            f"{event}.success",
            default=f"task {event} ok: #{res.task_id} → {res.to_state}",
            task_id=res.task_id,
            to_state=res.to_state,
            from_state=res.from_state,
            state_version=res.state_version,
            event_seq=res.event_seq,
            event=res.event,
            pool_key=extra.get("pool_key") or "-",
        )
        data = {
            "task_id": res.task_id,
            "from_state": res.from_state,
            "to_state": res.to_state,
            "event_seq": res.event_seq,
            "state_version": res.state_version,
            "event": res.event,
            "idempotent_replay": res.idempotent_replay,
            "correlation_id": res.correlation_id,
            "trace_id": res.trace_id,
        }
        if extra.get("pool_key"):
            data["pool_key"] = extra["pool_key"]
        return CommandResult.success_result(msg, data=data)
