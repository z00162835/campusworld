"""
F04: resolve npc_agent by handle (service_id or handle_aliases), with ambiguity and enabled checks.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.graph import Node


def normalize_handle(handle: str) -> str:
    return (handle or "").strip().lower()


def _enabled_allows(attrs: dict) -> bool:
    v = attrs.get("enabled")
    if v is False:
        return False
    if isinstance(v, str) and v.strip().lower() in ("false", "0", "no"):
        return False
    return True


def resolve_npc_agent_by_handle(session: Session, handle: str) -> Tuple[Optional[Node], Optional[str]]:
    """
    Find exactly one active npc_agent whose service_id or handle_aliases matches handle (normalized).

    Returns (node, None) on success, (None, error_message) on failure.
    Does not check decision_mode (callers enforce for NLP vs rules).
    """
    h = normalize_handle(handle)
    if not h:
        return None, "invalid agent handle"

    rows: List[Node] = (
        session.query(Node)
        .filter(
            Node.type_code == "npc_agent",
            Node.is_active == True,  # noqa: E712
        )
        .all()
    )

    matches: List[Node] = []
    seen: set[int] = set()
    for n in rows:
        attrs = dict(n.attributes or {})
        sid = str(attrs.get("service_id") or "").strip().lower()
        matched = False
        if sid == h:
            matched = True
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

    if len(matches) > 1:
        return None, f"ambiguous agent handle {h!r}; contact an administrator"

    if len(matches) == 0:
        return (
            None,
            f"unknown agent handle {h!r}. Type 'help' for available commands.",
        )

    node = matches[0]
    attrs = dict(node.attributes or {})
    if not _enabled_allows(attrs):
        return None, f"agent {h!r} is disabled"

    return node, None
