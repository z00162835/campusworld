from __future__ import annotations
from typing import Dict, Iterable, List, Sequence, Tuple
from app.game_engine.agent_runtime.tool_calling import ToolSchema
from app.game_engine.agent_runtime.tool_router.router_result import CandidateTier, RouterCandidate
_TIER_RANK: Dict[CandidateTier, int] = {CandidateTier.rerank: 3, CandidateTier.embedding: 2, CandidateTier.rule: 1, CandidateTier.slm: 0}

def merge_tiers(candidates: Iterable[RouterCandidate]) -> List[RouterCandidate]:
    """Sort by score descending; tie-break: rerank > embedding > rule > slm."""

    def key(c: RouterCandidate) -> Tuple[float, int]:
        return (float(c.score), _TIER_RANK.get(c.tier, 0))
    return sorted(candidates, key=key, reverse=True)

def dedupe_candidates(candidates: Iterable[RouterCandidate]) -> List[RouterCandidate]:
    """Keep highest (score, tier-rank) per tool_name."""
    best: Dict[str, RouterCandidate] = {}

    def key(c: RouterCandidate) -> Tuple[float, int]:
        return (float(c.score), _TIER_RANK.get(c.tier, 0))
    for c in candidates:
        prev = best.get(c.tool_name)
        if prev is None or key(c) > key(prev):
            best[c.tool_name] = c
    return merge_tiers(best.values())

def apply_schema_subset(schemas: Sequence[ToolSchema], allowed_names: Iterable[str]) -> List[ToolSchema]:
    """Filter schemas to allowed command names; preserve declaration order of ``schemas``."""
    allow = {str(x).strip() for x in allowed_names if str(x).strip()}
    if not allow:
        return list(schemas)
    return [s for s in schemas if getattr(s, 'name', None) in allow]
