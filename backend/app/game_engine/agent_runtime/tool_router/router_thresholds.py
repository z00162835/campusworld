"""F14 router ambiguity thresholds (versioned via ``ToolRouterConfig.threshold_revision``)."""
from __future__ import annotations
from app.game_engine.agent_runtime.tool_router.tool_router_config import ToolRouterConfig

def router_should_clarify(top_score: float, margin: float, cfg: ToolRouterConfig) -> bool:
    """Return True when routing should signal clarification (low margin or weak top score).

    ``threshold_revision`` is opaque metadata for logs and offline replay; this function
    reads numeric thresholds from ``cfg``.
    """
    if margin <= cfg.clarify_margin_max:
        return True
    min_top = cfg.clarify_min_top_score
    if min_top is not None and float(top_score) < float(min_top):
        return True
    return False

def router_confidence_heuristic(top_score: float, margin: float) -> float:
    """Scalar hint for Plan injection (legacy-compatible shape)."""
    return max(0.0, min(1.0, float(top_score) * (1.0 + min(0.5, float(margin)))))
