from __future__ import annotations

import pytest

from app.game_engine.agent_runtime.tool_calling import ToolSchema
from app.game_engine.agent_runtime.tool_router.pipeline import run_tool_router
from app.game_engine.agent_runtime.tool_router.router_result import EnforcementLevel
from app.game_engine.agent_runtime.tool_router.tool_router_config import ToolRouterConfig


@pytest.mark.unit
def test_run_tool_router_disabled_returns_none():
    cfg = ToolRouterConfig(enabled=False)
    schemas = [ToolSchema(name="look", description="x")]
    assert (
        run_tool_router(
            cfg=cfg,
            user_message="hello",
            world_snapshot="",
            stm_snippet=None,
            intent_hint={"intent": "informational"},
            tool_schemas=schemas,
            agent_extra={},
        )
        is None
    )


@pytest.mark.unit
def test_run_tool_router_stub_produces_candidates():
    cfg = ToolRouterConfig(enabled=True, k_default=4, k_info=2)
    schemas = [
        ToolSchema(name="look", description="see room"),
        ToolSchema(name="help", description="help cmd"),
        ToolSchema(name="whoami", description="user"),
    ]
    rr = run_tool_router(
        cfg=cfg,
        user_message="what is here",
        world_snapshot="room: lobby",
        stm_snippet=None,
        intent_hint={"intent": "execute"},
        tool_schemas=schemas,
        agent_extra={},
    )
    assert rr is not None
    assert len(rr.candidates) <= 4
    names = {c.tool_name for c in rr.candidates}
    assert names <= {"look", "help", "whoami"}


@pytest.mark.unit
def test_informational_shrinks_k():
    cfg = ToolRouterConfig(enabled=True, k_default=8, k_info=2)
    schemas = [ToolSchema(name=f"c{i}", description="d") for i in range(10)]
    rr = run_tool_router(
        cfg=cfg,
        user_message="hi",
        world_snapshot="",
        stm_snippet=None,
        intent_hint={"intent": "informational"},
        tool_schemas=schemas,
        agent_extra={},
    )
    assert rr is not None
    assert len(rr.candidates) <= 2


@pytest.mark.unit
def test_mandatory_intersects_resolved_tool_surface():
    """Rules may nominate tools absent from this tick's schema list; mandatory is clipped."""
    cfg = ToolRouterConfig(enabled=True, k_default=6, k_info=4)
    schemas = [
        ToolSchema(name="look", description="room"),
        ToolSchema(name="help", description="help"),
    ]
    rr = run_tool_router(
        cfg=cfg,
        user_message="inspect #42 node",
        world_snapshot="",
        stm_snippet=None,
        intent_hint={"intent": "informational"},
        tool_schemas=schemas,
        agent_extra={},
    )
    assert rr is not None
    assert "describe" not in rr.mandatory_tool_names
    assert rr.mandatory_tool_names == []


@pytest.mark.unit
def test_schema_allowlist_union():
    cfg = ToolRouterConfig(enabled=True, enforcement_level=EnforcementLevel.schema_subset)
    schemas = [ToolSchema(name="a", description=""), ToolSchema(name="b", description="")]
    rr = run_tool_router(
        cfg=cfg,
        user_message="x",
        world_snapshot="",
        stm_snippet=None,
        intent_hint={},
        tool_schemas=schemas,
        agent_extra={},
    )
    assert rr is not None
    allow = rr.schema_allowlist_names()
    assert set(allow) <= {"a", "b"}
