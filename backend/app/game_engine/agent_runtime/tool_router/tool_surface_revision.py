"""Stable fingerprint of the tool schema surface passed into F14 (SPEC §3.1 ``tool_registry_revision`` alias)."""

from __future__ import annotations

import hashlib
from typing import Sequence

from app.game_engine.agent_runtime.tool_calling import ToolSchema


def compute_tool_registry_revision(schemas: Sequence[ToolSchema]) -> str:
    """SHA-256 over sorted primary names + descriptions (first 16 hex chars).

    Intended for logs / replay when manifest revision is not wired into the tick.
    Bump descriptions or tool set changes the revision.
    """
    rows: list[str] = []
    for s in sorted(schemas, key=lambda x: (getattr(x, "name", "") or "").lower()):
        name = (getattr(s, "name", "") or "").strip()
        desc = (getattr(s, "description", "") or "").strip()
        rows.append(f"{name}\x1f{desc}")
    blob = "\x1e".join(rows).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]
