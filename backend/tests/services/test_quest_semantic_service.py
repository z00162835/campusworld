"""Unit tests for the R1 Situation trigger semantics."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.task.errors import PreconditionFailed
from app.services.task.quest_semantic_service import (
    create_goal,
    create_quest,
    explicit_node_id_ref,
    resolve_semantic_node_ref,
    split_semantic_ref,
    summarize_objective_progress,
    validate_situation_semantics,
)


@pytest.mark.unit
def test_situation_requires_assertion():
    with pytest.raises(PreconditionFailed, match="assertion"):
        validate_situation_semantics(assertion="", trigger_kind="manual")


@pytest.mark.unit
def test_hard_rule_requires_fact_or_evidence_and_rule_ref():
    with pytest.raises(PreconditionFailed, match="fact_ref"):
        validate_situation_semantics(
            assertion="Room temperature exceeds comfort range.",
            trigger_kind="hard_rule",
            rule_refs=["policy:temperature@v1"],
        )
    with pytest.raises(PreconditionFailed, match="rule_ref"):
        validate_situation_semantics(
            assertion="Room temperature exceeds comfort range.",
            trigger_kind="hard_rule",
            fact_refs=["fact:room-101-temperature"],
        )


@pytest.mark.unit
def test_weak_experience_requires_fact_or_evidence_and_experience_or_inference():
    with pytest.raises(PreconditionFailed, match="fact_ref"):
        validate_situation_semantics(
            assertion="A recurring compressor pattern is forming.",
            trigger_kind="weak_experience",
            experience_refs=["case:similar-compressor-drift"],
        )
    with pytest.raises(PreconditionFailed, match="experience_ref"):
        validate_situation_semantics(
            assertion="A recurring compressor pattern is forming.",
            trigger_kind="weak_experience",
            fact_refs=["fact:vibration-window"],
        )


@pytest.mark.unit
def test_manual_situation_can_be_created_without_rule_or_experience_refs():
    validate_situation_semantics(
        assertion="The facility manager reports intermittent noise near AHU-3.",
        trigger_kind="manual",
    )


@pytest.mark.unit
def test_mixed_requires_rule_and_weak_experience_sources():
    with pytest.raises(PreconditionFailed, match="rule_ref"):
        validate_situation_semantics(
            assertion="Temperature breach repeats a known after-hours pattern.",
            trigger_kind="mixed",
            fact_refs=["fact:ahu-3-temperature"],
            experience_refs=["pattern:after-hours-drift"],
        )
    with pytest.raises(PreconditionFailed, match="experience_ref"):
        validate_situation_semantics(
            assertion="Temperature breach repeats a known after-hours pattern.",
            trigger_kind="mixed",
            fact_refs=["fact:ahu-3-temperature"],
            rule_refs=["quality:comfort-band@v2"],
        )
    validate_situation_semantics(
        assertion="Temperature breach repeats a known after-hours pattern.",
        trigger_kind="mixed",
        fact_refs=["fact:ahu-3-temperature"],
        rule_refs=["quality:comfort-band@v2"],
        inference_trace_summary="Matched after-hours drift pattern from prior cases.",
    )


@pytest.mark.unit
def test_rule_refs_must_be_version_pinned():
    with pytest.raises(PreconditionFailed, match="namespace:key@version"):
        validate_situation_semantics(
            assertion="Temperature breach exceeds a policy threshold.",
            trigger_kind="hard_rule",
            fact_refs=["fact:ahu-3-temperature"],
            rule_refs=["quality:comfort-band"],
        )


@pytest.mark.unit
def test_experience_refs_must_be_version_pinned():
    with pytest.raises(PreconditionFailed, match="experience_refs"):
        validate_situation_semantics(
            assertion="Temperature breach repeats a known pattern.",
            trigger_kind="weak_experience",
            fact_refs=["fact:ahu-3-temperature"],
            experience_refs=["case:after-hours-drift"],
        )


@pytest.mark.unit
def test_goal_requires_desired_state_before_db_access():
    with pytest.raises(PreconditionFailed, match="desired_state"):
        create_goal(
            title="Incomplete goal",
            situation_id=1,
            actor=object(),  # type: ignore[arg-type]
            desired_state="",
        )


@pytest.mark.unit
def test_quest_risk_level_uses_r1_enum():
    with pytest.raises(PreconditionFailed, match="risk_level"):
        create_quest(
            title="Unsafe risk enum",
            situation_id=1,
            goal_id=2,
            actor=object(),  # type: ignore[arg-type]
            risk_level="emergency",
        )


@pytest.mark.unit
def test_quest_governance_refs_must_be_version_pinned_before_db_access():
    with pytest.raises(PreconditionFailed, match="policy_refs"):
        create_quest(
            title="Unpinned policy quest",
            situation_id=1,
            goal_id=2,
            actor=object(),  # type: ignore[arg-type]
            policy_refs=["policy:maintenance_safety"],
        )
    with pytest.raises(PreconditionFailed, match="process_refs"):
        create_quest(
            title="Unpinned process quest",
            situation_id=1,
            goal_id=2,
            actor=object(),  # type: ignore[arg-type]
            process_refs=["process:bearing_response"],
        )
    with pytest.raises(PreconditionFailed, match="quality_refs"):
        create_quest(
            title="Unpinned quality quest",
            situation_id=1,
            goal_id=2,
            actor=object(),  # type: ignore[arg-type]
            quality_refs=["quality:post_maintenance"],
        )
    with pytest.raises(PreconditionFailed, match="case_refs"):
        create_quest(
            title="Unpinned case quest",
            situation_id=1,
            goal_id=2,
            actor=object(),  # type: ignore[arg-type]
            case_refs=["case:AHU-103"],
        )


@pytest.mark.unit
def test_objective_progress_splits_terminal_and_succeeded_states():
    progress = summarize_objective_progress(["done", "failed", "cancelled", "claimed"])

    assert progress["total_objectives"] == 4
    assert progress["terminal_objectives"] == 3
    assert progress["completed_objectives"] == 1
    assert progress["succeeded_objectives"] == 1
    assert progress["failed_objectives"] == 1
    assert progress["cancelled_objectives"] == 1
    assert progress["percent"] == 75
    assert progress["success_percent"] == 25


@pytest.mark.unit
def test_semantic_ref_parser_supports_namespace_key_version():
    assert split_semantic_ref("policy:maintenance_safety@3.2") == (
        "policy",
        "maintenance_safety",
        "3.2",
    )
    assert split_semantic_ref("case:AHU-103:2026Q2") == (
        "case",
        "AHU-103:2026Q2",
        None,
    )
    assert split_semantic_ref("plain-key") == (None, "plain-key", None)


@pytest.mark.unit
def test_explicit_node_id_ref_parser():
    assert explicit_node_id_ref("123") == 123
    assert explicit_node_id_ref("node:123") == 123
    assert explicit_node_id_ref("#123") == 123
    assert explicit_node_id_ref("policy:123") is None


@pytest.mark.unit
def test_namespaced_semantic_ref_does_not_fallback_to_unrelated_key_match():
    class FakeResult:
        def all(self):
            return [
                SimpleNamespace(
                    id=42,
                    type_code="default_object",
                    attributes={"key": "maintenance_safety", "version": "3.2"},
                )
            ]

    class FakeSession:
        def execute(self, *_args, **_kwargs):
            return FakeResult()

    assert resolve_semantic_node_ref(FakeSession(), "policy:maintenance_safety@3.2") is None


@pytest.mark.unit
def test_namespaced_semantic_ref_accepts_exact_ref_across_storage_node_types():
    class FakeResult:
        def all(self):
            return [
                SimpleNamespace(
                    id=42,
                    type_code="default_object",
                    attributes={"semantic_ref": "policy:maintenance_safety@3.2"},
                )
            ]

    class FakeSession:
        def execute(self, *_args, **_kwargs):
            return FakeResult()

    assert resolve_semantic_node_ref(FakeSession(), "policy:maintenance_safety@3.2") == 42
