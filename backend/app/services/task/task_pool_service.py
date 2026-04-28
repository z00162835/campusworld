"""Task pool read-side service (Phase B minimal).

SSOT: ``docs/task/SPEC/features/F05_TASK_POOL_FIRST_CLASS_REGISTRY.md``.

Only read helpers are exposed in Phase B; pool admin (``create / update /
disable / enable``) is performed by the command layer (PR5) which writes
``task_pools`` directly. Per plan §3 PR3 CI guard, ``task_pools`` is *not*
on the protected-write list (it is admin-managed metadata, not a derivative
of state-machine activity).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def list_pools(
    session: Session,
    *,
    include_inactive: bool = False,
    key_prefix: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Return pool metadata rows ordered by ``key`` ascending."""
    sql = """
        SELECT id, key, display_name, description, is_active,
               default_workflow_ref, default_visibility, default_priority,
               publish_acl, consume_acl, attributes,
               created_at, updated_at
          FROM task_pools
         WHERE 1 = 1
    """
    params: Dict[str, Any] = {"limit": int(limit), "offset": int(offset)}
    if not include_inactive:
        sql += " AND is_active = TRUE"
    if key_prefix:
        sql += " AND key LIKE :prefix"
        params["prefix"] = f"{key_prefix}%"
    sql += " ORDER BY key ASC LIMIT :limit OFFSET :offset"

    rows = session.execute(text(sql), params).all()
    return [_row_to_dict(r) for r in rows]


def get_pool_by_key(session: Session, key: str) -> Optional[Dict[str, Any]]:
    row = session.execute(
        text(
            """
            SELECT id, key, display_name, description, is_active,
                   default_workflow_ref, default_visibility, default_priority,
                   publish_acl, consume_acl, attributes,
                   created_at, updated_at
              FROM task_pools
             WHERE key = :k
            """
        ),
        {"k": key},
    ).first()
    if row is None:
        return None
    return _row_to_dict(row)


def _row_to_dict(row) -> Dict[str, Any]:
    def _maybe_json(v):
        if v is None or isinstance(v, (dict, list)):
            return v
        try:
            return json.loads(v)
        except (TypeError, ValueError):
            return v

    return {
        "id": int(row[0]),
        "key": row[1],
        "display_name": row[2],
        "description": row[3],
        "is_active": bool(row[4]),
        "default_workflow_ref": _maybe_json(row[5]),
        "default_visibility": row[6],
        "default_priority": row[7],
        "publish_acl": _maybe_json(row[8]),
        "consume_acl": _maybe_json(row[9]),
        "attributes": _maybe_json(row[10]),
        "created_at": row[11],
        "updated_at": row[12],
    }


__all__ = ["list_pools", "get_pool_by_key"]
