"""Stable short fingerprint for LLM cache invalidation (per-loop-phase)."""
from __future__ import annotations
import hashlib
from typing import Optional

def compute_npc_prompt_fingerprint(*, world_snapshot: str, tool_manifest_text: str, user_message: str, skill_context_text: Optional[str] = None, phase: Optional[str] = None) -> str:
    """Per-loop-phase input-side hash for trace/dedup integrity.

    Inputs: platform system is not hashed here (stable per config); the hashed
    set is the per-phase user/input context — world snapshot, tool manifest,
    skill-context (L1 manifest + L2 body), and a bounded slice of the user
    message — plus the phase label so identical inputs across phases do not
    collide. The fingerprint is stripped before HTTP and is NOT a v1
    correctness contract; it exists for trace/dedup integrity and forward
    compatibility with future prompt-cache keys.
    """
    raw = f"phase={phase or ''}\n{world_snapshot}\n{tool_manifest_text}\n{skill_context_text or ''}\n{(user_message or '')[:512]}"
    return hashlib.sha256(raw.encode('utf-8', errors='replace')).hexdigest()[:48]
