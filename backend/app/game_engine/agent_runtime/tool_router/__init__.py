"""Pre-Plan tool routing: recall, rerank, mandatory hints, optional schema narrowing.

Contract alignment: see docs under docs/models/SPEC/features/ for tool router design.
"""

from app.game_engine.agent_runtime.tool_router.merge import apply_schema_subset, merge_tiers
from app.game_engine.agent_runtime.tool_router.pipeline import format_tool_router_hint, run_tool_router
from app.game_engine.agent_runtime.tool_router.router_result import (
    CandidateTier,
    EnforcementLevel,
    RouterCandidate,
    RouterResult,
)
from app.game_engine.agent_runtime.tool_router.tool_router_config import ToolRouterConfig, parse_tool_router_config

__all__ = [
    "CandidateTier",
    "EnforcementLevel",
    "RouterCandidate",
    "RouterResult",
    "ToolRouterConfig",
    "apply_schema_subset",
    "merge_tiers",
    "parse_tool_router_config",
    "format_tool_router_hint",
    "run_tool_router",
]
