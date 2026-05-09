from __future__ import annotations

import pytest

from app.game_engine.agent_runtime.tool_calling import ToolSchema
from app.game_engine.agent_runtime.tool_router.tool_surface_revision import compute_tool_registry_revision


@pytest.mark.unit
def test_registry_revision_stable_for_same_surface():
    s = [
        ToolSchema(name="b", description="two"),
        ToolSchema(name="a", description="one"),
    ]
    assert compute_tool_registry_revision(s) == compute_tool_registry_revision(list(reversed(s)))


@pytest.mark.unit
def test_registry_revision_changes_when_description_changes():
    a = [ToolSchema(name="x", description="old")]
    b = [ToolSchema(name="x", description="new")]
    assert compute_tool_registry_revision(a) != compute_tool_registry_revision(b)
