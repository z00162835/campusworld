"""Stable short fingerprint for LLM cache invalidation (F12 D19)."""

from __future__ import annotations

import hashlib


def compute_npc_prompt_fingerprint(
    *,
    world_snapshot: str,
    tool_manifest_text: str,
    user_message: str,
) -> str:
    raw = f"{world_snapshot}\n{tool_manifest_text}\n{(user_message or '')[:512]}"
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:48]
