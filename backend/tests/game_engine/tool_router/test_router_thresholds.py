from __future__ import annotations

import pytest

from app.game_engine.agent_runtime.tool_router.router_thresholds import router_should_clarify
from app.game_engine.agent_runtime.tool_router.tool_router_config import ToolRouterConfig


@pytest.mark.unit
def test_clarify_when_margin_at_or_below_max():
    cfg = ToolRouterConfig(clarify_margin_max=0.05)
    assert router_should_clarify(0.9, 0.05, cfg) is True
    assert router_should_clarify(0.9, 0.06, cfg) is False


@pytest.mark.unit
def test_clarify_when_top_below_min():
    cfg = ToolRouterConfig(clarify_margin_max=0.0, clarify_min_top_score=0.5)
    assert router_should_clarify(0.49, 1.0, cfg) is True
    assert router_should_clarify(0.5, 1.0, cfg) is False


@pytest.mark.unit
def test_threshold_revision_is_opaque_metadata():
    cfg = ToolRouterConfig(threshold_revision="2026-05-07.t1", clarify_margin_max=0.01)
    assert router_should_clarify(1.0, 0.02, cfg) is False
