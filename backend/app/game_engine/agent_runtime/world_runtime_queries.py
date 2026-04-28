"""Read-only graph queries shared by world snapshot and system primer annex.

Kept free of AICO-specific naming so ``primer`` and per-tick snapshot stay aligned.
"""

from __future__ import annotations

from typing import List, Tuple

from app.models.graph import Node


def installed_worlds_from_session(session) -> List[Tuple[str, str]]:
    """Return ``(world_id, display_label)`` pairs from active ``world_entrance`` nodes.

    Ordering follows database row order (stable enough for UI); callers may sort.
    """
    out: List[Tuple[str, str]] = []
    if session is None:
        return out
    try:
        rows = (
            session.query(Node)
            .filter(
                Node.type_code == "world_entrance",
                Node.is_active == True,  # noqa: E712
            )
            .limit(32)
            .all()
        )
        for n in rows:
            attrs = n.attributes or {}
            wid = str(attrs.get("world_id") or n.name or "").strip()
            if not wid:
                continue
            root_name = str(attrs.get("target_display_name") or n.name or wid)
            out.append((wid, root_name))
    except Exception:
        return []
    return out
