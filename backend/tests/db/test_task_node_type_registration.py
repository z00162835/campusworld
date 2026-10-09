"""Phase B PR1: task node type registration in graph_seed_node_types.yaml.

Pure-unit checks; no DB. Mirrors docs/task/SPEC/features/F01 §3 + §7.
"""

from __future__ import annotations

import pytest

from app.constants.trait_mask import (
    CONCEPTUAL,
    EVENT_BASED,
    TASK,
    TASK_MARKER,
)
from db.ontology.load import load_graph_seed_node_type_overrides


_REQUIRED_PROPERTIES = (
    "current_state",
    "state_version",
    "workflow_ref",
    "title",
    "priority",
    "due_at",
    "assignee_kind",
    "scope_selector",
    "visibility",
    "tags",
    "children_summary",
    "pool_id",
)

# Fields that must NEVER appear on the task node attributes (F01 §3 禁列字段).
_BANNED_PROPERTIES = (
    "description_md",
    "assignees",
    "history",
    "transitions",
    "runs",
    "command_trace",
    "events",
    "comments",
)

_SEMANTIC_NODE_REQUIRED_PROPERTIES = {
    "situation": {
        "current_state",
        "state_version",
        "title",
        "assertion",
        "subject_ref",
        "trigger_kind",
        "trigger_summary",
        "fact_refs",
        "evidence_refs",
        "rule_refs",
        "experience_refs",
        "inference_trace_summary",
        "confidence",
        "severity",
        "business_impact",
        "temporal_scope",
        "actor_provenance",
        "asserted_at",
    },
    "goal": {
        "current_state",
        "state_version",
        "title",
        "desired_state",
        "constraints",
        "priority",
        "deadline_at",
        "owner_principal",
        "acceptance_summary",
        "situation_id",
        "created_by",
        "created_at",
    },
    "quest": {
        "current_state",
        "state_version",
        "title",
        "situation_id",
        "goal_id",
        "risk_level",
        "progress",
        "quest_ref",
        "plan_graph_summary",
        "policy_refs",
        "process_refs",
        "quality_refs",
        "case_refs",
        "outcome_summary",
        "created_by",
        "created_at",
    },
}

_SEMANTIC_NODE_INITIAL_STATES = {
    "situation": "asserted",
    "goal": "proposed",
    "quest": "draft",
}


@pytest.mark.unit
def test_task_overlay_present_with_correct_trait():
    ov = load_graph_seed_node_type_overrides()
    assert "task" in ov, "task node type must be registered in graph_seed_node_types.yaml"
    entry = ov["task"]
    assert entry["trait_class"] == "TASK"
    assert int(entry["trait_mask"]) == TASK
    assert int(entry["trait_mask"]) == 1089


@pytest.mark.unit
def test_task_schema_required_fields():
    ov = load_graph_seed_node_type_overrides()
    sd = ov["task"]["schema_definition"]
    assert sd["type"] == "object"
    props = sd["properties"]
    for name in _REQUIRED_PROPERTIES:
        assert name in props, f"task schema missing required property: {name}"


@pytest.mark.unit
def test_task_schema_no_banned_fields():
    ov = load_graph_seed_node_type_overrides()
    sd = ov["task"]["schema_definition"]
    props = sd["properties"]
    for banned in _BANNED_PROPERTIES:
        assert banned not in props, (
            f"task schema must not register {banned}; "
            "see docs/task/SPEC/features/F01 §3 禁列字段"
        )


@pytest.mark.unit
def test_task_priority_enum_matches_spec():
    ov = load_graph_seed_node_type_overrides()
    sd = ov["task"]["schema_definition"]
    enum = sd["properties"]["priority"]["enum"]
    assert set(enum) == {"low", "normal", "high", "urgent"}


@pytest.mark.unit
def test_task_assignee_kind_enum_matches_spec():
    ov = load_graph_seed_node_type_overrides()
    sd = ov["task"]["schema_definition"]
    enum = sd["properties"]["assignee_kind"]["enum"]
    assert set(enum) == {"user", "agent", "pool", "group"}


@pytest.mark.unit
def test_task_visibility_enum_matches_spec():
    ov = load_graph_seed_node_type_overrides()
    sd = ov["task"]["schema_definition"]
    enum = sd["properties"]["visibility"]["enum"]
    assert set(enum) == {
        "private",
        "explicit",
        "role_scope",
        "world_scope",
        "pool_open",
    }


@pytest.mark.unit
def test_task_marker_bit_does_not_collide_with_existing_bits():
    # TASK_MARKER must be a single bit, distinct from existing bit0..bit9 set used by other types.
    assert TASK_MARKER == 1 << 10
    # Existing semantic bits (CONCEPTUAL=1, EVENT_BASED=64) must remain disjoint with the marker.
    assert CONCEPTUAL & TASK_MARKER == 0
    assert EVENT_BASED & TASK_MARKER == 0


@pytest.mark.unit
def test_task_node_type_is_importable_from_constants():
    # Hard-pin the SPEC requirement that `from app.constants.trait_mask import TASK` works.
    from app.constants.trait_mask import TASK as TASK_IMPORTED

    assert TASK_IMPORTED == 1089


@pytest.mark.unit
def test_quest_semantic_node_overlays_present_with_task_trait():
    ov = load_graph_seed_node_type_overrides()
    for type_code in ("situation", "goal", "quest"):
        assert type_code in ov, f"{type_code} node type must be registered"
        entry = ov[type_code]
        assert entry["trait_class"] == "TASK"
        assert int(entry["trait_mask"]) == TASK


@pytest.mark.unit
def test_quest_semantic_node_schema_covers_service_attributes():
    ov = load_graph_seed_node_type_overrides()
    for type_code, required in _SEMANTIC_NODE_REQUIRED_PROPERTIES.items():
        props = ov[type_code]["schema_definition"]["properties"]
        missing = sorted(required.difference(props))
        assert missing == [], f"{type_code} schema missing service-written attributes: {missing}"


@pytest.mark.unit
def test_quest_semantic_node_initial_states_match_service_and_schema():
    from app.services.task.quest_semantic_service import SEMANTIC_NODE_INITIAL_STATES

    assert SEMANTIC_NODE_INITIAL_STATES == _SEMANTIC_NODE_INITIAL_STATES
    ov = load_graph_seed_node_type_overrides()
    for type_code, initial_state in _SEMANTIC_NODE_INITIAL_STATES.items():
        state_enum = ov[type_code]["schema_definition"]["properties"]["current_state"]["enum"]
        assert initial_state in state_enum


@pytest.mark.unit
def test_quest_semantic_node_enums_match_service_contract():
    ov = load_graph_seed_node_type_overrides()
    situation_props = ov["situation"]["schema_definition"]["properties"]
    goal_props = ov["goal"]["schema_definition"]["properties"]
    quest_props = ov["quest"]["schema_definition"]["properties"]

    assert set(situation_props["trigger_kind"]["enum"]) == {
        "hard_rule",
        "weak_experience",
        "manual",
        "mixed",
    }
    assert set(situation_props["severity"]["enum"]) == {"low", "medium", "high", "critical"}
    assert set(goal_props["priority"]["enum"]) == {"low", "normal", "high", "urgent"}
    assert set(quest_props["risk_level"]["enum"]) == {"low", "normal", "high", "critical"}


@pytest.mark.unit
def test_goal_desired_state_schema_is_not_nullable():
    ov = load_graph_seed_node_type_overrides()
    desired_state_type = ov["goal"]["schema_definition"]["properties"]["desired_state"]["type"]
    assert set(desired_state_type) == {"object", "string"}


@pytest.mark.unit
def test_situation_business_impact_schema_matches_spec():
    ov = load_graph_seed_node_type_overrides()
    business_impact_type = ov["situation"]["schema_definition"]["properties"]["business_impact"]["type"]
    assert set(business_impact_type) == {"object", "string", "null"}
