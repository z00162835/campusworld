from __future__ import annotations

import pytest

from app.game_engine.agent_runtime.tool_calling import ToolSchema
from app.game_engine.agent_runtime.tool_router.merge import (
    apply_schema_subset,
    dedupe_candidates,
    merge_tiers,
)
from app.game_engine.agent_runtime.tool_router.router_result import CandidateTier, RouterCandidate
from app.game_engine.agent_runtime.tool_router.tool_router_config import parse_tool_router_config


@pytest.mark.unit
def test_merge_tiers_prefers_higher_tier_on_tie():
    a = RouterCandidate("a", 0.5, CandidateTier.rule)
    b = RouterCandidate("b", 0.5, CandidateTier.rerank)
    out = merge_tiers([a, b])
    assert out[0].tool_name == "b"


@pytest.mark.unit
def test_dedupe_keeps_best_score():
    a = RouterCandidate("look", 0.2, CandidateTier.embedding)
    b = RouterCandidate("look", 0.9, CandidateTier.rule)
    out = dedupe_candidates([a, b])
    assert len(out) == 1
    assert out[0].score == 0.9


@pytest.mark.unit
def test_apply_schema_subset_order():
    schemas = [
        ToolSchema(name="look", description=""),
        ToolSchema(name="whoami", description=""),
        ToolSchema(name="help", description=""),
    ]
    f = apply_schema_subset(schemas, ["whoami", "look"])
    assert [s.name for s in f] == ["look", "whoami"]


@pytest.mark.unit
def test_parse_tool_router_defaults_off():
    cfg = parse_tool_router_config({"tool_router": {"enabled": False}})
    assert cfg.enabled is False
    cfg_on = parse_tool_router_config({"tool_router": {"enabled": True, "k_info": 6}})
    assert cfg_on.enabled is True
    assert cfg_on.k_info == 6


@pytest.mark.unit
def test_parse_router_thresholds_nested_and_flat():
    cfg = parse_tool_router_config(
        {
            "tool_router": {
                "enabled": True,
                "threshold_revision": "t-v2",
                "router_thresholds": {"clarify_margin_max": 0.02, "clarify_min_top_score": 0.4},
            }
        }
    )
    assert cfg.threshold_revision == "t-v2"
    assert cfg.clarify_margin_max == 0.02
    assert cfg.clarify_min_top_score == 0.4
    cfg2 = parse_tool_router_config(
        {"tool_router": {"clarify_margin_max": 0.08, "clarify_min_top_score": 0.1}}
    )
    assert cfg2.clarify_margin_max == 0.08
    assert cfg2.clarify_min_top_score == 0.1
