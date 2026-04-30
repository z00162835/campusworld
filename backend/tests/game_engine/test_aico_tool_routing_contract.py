from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.game_engine.agent_runtime.system_primer_context import build_ontology_primer, primer_toc
from app.game_engine.agent_runtime.frameworks.llm_pdca import _assemble_plan_user


def _settings_yaml() -> dict:
    p = Path(__file__).resolve().parents[2] / "config" / "settings.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


@pytest.mark.unit
def test_aico_prompt_contains_intent_routing_rules():
    data = _settings_yaml()
    aico = data["agents"]["llm"]["by_service_id"]["aico"]
    system_prompt = aico["system_prompt"]
    plan = aico["phase_prompts"]["plan"]
    assert "epistemic necessity" in system_prompt.lower()
    assert "help <cmd>" in system_prompt
    assert "informational / verify_state / execute" in plan


@pytest.mark.unit
def test_primer_commands_section_is_exposed_with_alias():
    keys = [key for key, _ in primer_toc()]
    assert "commands" in keys
    body = build_ontology_primer(section="commands")
    assert "help <command>" in body
    # backward compatibility for callers still using the old key.
    body_alias = build_ontology_primer(section="examples")
    assert body_alias == body


@pytest.mark.unit
def test_plan_prompt_hard_separates_intent_tool_classes():
    data = _settings_yaml()
    plan = data["agents"]["llm"]["by_service_id"]["aico"]["phase_prompts"]["plan"]
    assert "never plan mutate tools" in plan
    assert "verify_state requests, use read-only tools only" in plan


@pytest.mark.unit
def test_plan_user_contains_structured_intent_hint():
    assembled = _assemble_plan_user(
        user_msg="给一个task创建例子",
        memory="",
        world_snapshot="",
        tool_manifest_text="",
        intent_hint={"intent": "informational", "reason_tokens": ["informational_cue"]},
    )
    assert "Intent hint (runtime pre-classifier):" in assembled
    assert "intent: informational" in assembled
