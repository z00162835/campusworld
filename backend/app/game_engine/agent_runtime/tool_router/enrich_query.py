from __future__ import annotations

from typing import List, Optional


def build_enrich_query_text(
    *,
    user_message: str,
    world_snapshot: str,
    stm_snippet: Optional[str],
    rule_hints: List[str],
    entity_spans: List[str],
    lexicon_hits: List[str],
) -> str:
    """Serialize retrieval query (snapshot-first ordering for cache-friendly blocks)."""
    parts: List[str] = []
    ws = (world_snapshot or "").strip()
    if ws:
        parts.append(f"World snapshot:\n{ws}")
    if rule_hints:
        parts.append("Rule hints:\n" + "\n".join(f"- {h}" for h in rule_hints))
    if entity_spans:
        parts.append("Entity hints:\n" + ", ".join(entity_spans[:64]))
    if lexicon_hits:
        parts.append("Lexicon align:\n" + ", ".join(lexicon_hits[:32]))
    stm = (stm_snippet or "").strip()
    if stm:
        parts.append(f"STM snippet:\n{stm}")
    um = (user_message or "").strip()
    if um:
        parts.append(f"User message:\n{um}")
    return "\n\n".join(parts)
