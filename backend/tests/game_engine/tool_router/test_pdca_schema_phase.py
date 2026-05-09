from __future__ import annotations

import pytest

from app.game_engine.agent_runtime.frameworks.llm_pdca import resolve_tool_schemas_for_pdca_phase
from app.game_engine.agent_runtime.frameworks.pdca import PDCAPhase
from app.game_engine.agent_runtime.tool_calling import ToolSchema


@pytest.mark.unit
def test_schema_subset_applies_only_on_plan_phase():
    schemas = [
        ToolSchema(name="look", description=""),
        ToolSchema(name="describe", description=""),
    ]
    payload = {"pdca_tool_schema_allowlist": ["look"]}
    plan_only = resolve_tool_schemas_for_pdca_phase(schemas, payload, PDCAPhase.plan.value)
    assert [s.name for s in plan_only] == ["look"]
    full_do = resolve_tool_schemas_for_pdca_phase(schemas, payload, PDCAPhase.do.value)
    assert [s.name for s in full_do] == ["look", "describe"]
    full_check = resolve_tool_schemas_for_pdca_phase(schemas, payload, PDCAPhase.check.value)
    assert len(full_check) == 2


@pytest.mark.unit
def test_schema_subset_empty_allowlist_falls_back_full():
    schemas = [ToolSchema(name="a", description="")]
    assert len(resolve_tool_schemas_for_pdca_phase(schemas, {}, PDCAPhase.plan.value)) == 1
