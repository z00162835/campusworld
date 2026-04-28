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
