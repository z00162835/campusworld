"""User task queue view for CampusWorld world interaction UI.

The queue is not a separate table; it uses ``task_visibility_sql`` (Task SPEC
§1.5) without ``task list --mine`` / ``--assigned`` narrowing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.commands.base import CommandContext
from app.commands.game.task._helpers import principal_from_context
from app.services.task.permissions import Principal
from app.services.task.task_visibility_sql import (
    VISIBILITY_PREDICATE_SQL,
    compute_visible_pool_ids,
)

_TASK_LIST_MAX_LIMIT = 50


@dataclass(frozen=True)
class QueueTaskRow:
    id: int
    state: str
    title: str
    priority: str
    pool_key: Optional[str]
    visibility: str
    assignee_kind: str


def principal_from_actor(*, user_id: str, roles: Sequence[str], permissions: Sequence[str]) -> Principal:
    ctx = CommandContext(
        user_id=user_id,
        username="",
        session_id="",
        permissions=list(permissions),
        roles=list(roles),
    )
    return principal_from_context(ctx)


def list_for_principal(
    session: Session,
    actor: Principal,
    *,
    limit: int = 20,
    offset: int = 0,
    actionable_only: bool = True,
) -> List[QueueTaskRow]:
    """Return tasks visible in the caller's queue."""
    visible_pool_ids = compute_visible_pool_ids(session, actor)
    params: Dict[str, Any] = {
        "pid": actor.id,
        "pkind": actor.kind,
        "visible_pool_ids": visible_pool_ids or [0],
        "limit": max(1, min(limit, _TASK_LIST_MAX_LIMIT)),
        "offset": max(0, offset),
    }
    state_clause = ""
    if actionable_only:
        state_clause = " AND n.attributes->>'current_state' NOT IN ('done', 'cancelled', 'failed')"
    sql = f"""
        SELECT n.id,
               n.attributes->>'current_state' AS state,
               n.attributes->>'title' AS title,
               n.attributes->>'priority' AS priority,
               n.attributes->>'visibility' AS visibility,
               n.attributes->>'assignee_kind' AS assignee_kind,
               p.key AS pool_key
          FROM nodes n
     LEFT JOIN task_pools p ON p.id = (n.attributes->>'pool_id')::bigint
         WHERE n.type_code = 'task'
           AND n.is_active = TRUE
           AND {VISIBILITY_PREDICATE_SQL}
           {state_clause}
      ORDER BY
        CASE n.attributes->>'priority'
          WHEN 'urgent' THEN 0 WHEN 'high' THEN 1
          WHEN 'normal' THEN 2 WHEN 'low' THEN 3
          ELSE 4
        END,
        n.created_at ASC
         LIMIT :limit OFFSET :offset
    """
    rows = session.execute(text(sql), params).all()
    return [
        QueueTaskRow(
            id=int(row.id),
            state=str(row.state or "open"),
            title=str(row.title or row.id),
            priority=str(row.priority or "normal"),
            pool_key=str(row.pool_key) if row.pool_key else None,
            visibility=str(row.visibility or ""),
            assignee_kind=str(row.assignee_kind or ""),
        )
        for row in rows
    ]


def last_handled_task(
    session: Session,
    actor: Principal,
) -> Optional[Dict[str, Any]]:
    """Most recent task the actor moved to done or cancelled."""
    row = session.execute(
        text(
            """
            SELECT n.id,
                   n.attributes->>'title' AS title,
                   tst.to_state AS to_state,
                   tst.created_at AS handled_at
              FROM task_state_transitions tst
              JOIN nodes n ON n.id = tst.task_node_id
             WHERE tst.actor_principal_id = :pid
               AND tst.actor_principal_kind = :pkind
               AND tst.to_state IN ('done', 'cancelled')
             ORDER BY tst.created_at DESC
             LIMIT 1
            """
        ),
        {"pid": actor.id, "pkind": actor.kind},
    ).first()
    if not row:
        return None
    handled_at = row.handled_at.isoformat() + "Z" if row.handled_at else None
    return {
        "id": str(row.id),
        "title": str(row.title or row.id),
        "status": str(row.to_state),
        "handledAt": handled_at,
    }
