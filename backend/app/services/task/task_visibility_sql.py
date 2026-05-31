"""Shared task list visibility SQL (Phase B).

SSOT for the visibility fragment used by ``task list``, ``user_task_queue``, and
World UI aggregation. Aligns with ``docs/task/SPEC/SPEC.md`` §1.5 and pool
definition (no active ``executor`` on ``pool_open`` slots).

Parameters bound by callers: ``:pid``, ``:pkind``, ``:visible_pool_ids``.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.task.acl import evaluate_acl
from app.services.task.permissions import Principal

# Fragment referencing outer alias ``n`` (task node row).
VISIBILITY_PREDICATE_SQL = """
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
    AND NOT EXISTS (
      SELECT 1 FROM task_assignments a
       WHERE a.task_node_id = n.id
         AND a.is_active
         AND a.role = 'executor'
    )
  )
)
"""


def decode_jsonb(value: Any) -> Dict[str, Any]:
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


def compute_visible_pool_ids(session: Session, actor: Principal) -> List[int]:
    """Return pool ids whose ``consume_acl`` allows ``actor``."""
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
    for row in rows:
        acl = decode_jsonb(row.consume_acl)
        if evaluate_acl(actor, acl).allow:
            out.append(int(row.id))
    return out


def pool_open_has_active_executor(session: Session, task_node_id: int) -> bool:
    row = session.execute(
        text(
            """
            SELECT 1
              FROM task_assignments a
             WHERE a.task_node_id = :tid
               AND a.is_active
               AND a.role = 'executor'
             LIMIT 1
            """
        ),
        {"tid": task_node_id},
    ).first()
    return row is not None


__all__ = [
    "VISIBILITY_PREDICATE_SQL",
    "compute_visible_pool_ids",
    "decode_jsonb",
    "pool_open_has_active_executor",
]
