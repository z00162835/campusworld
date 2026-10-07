"""Unit tests for the R1 Situation trigger semantics."""
from __future__ import annotations

import pytest

from app.services.task.errors import PreconditionFailed
from app.services.task.quest_semantic_service import validate_situation_semantics


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
            rule_refs=["policy:temperature:v1"],
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
            rule_refs=["quality:comfort-band:v2"],
        )
    validate_situation_semantics(
        assertion="Temperature breach repeats a known after-hours pattern.",
        trigger_kind="mixed",
        fact_refs=["fact:ahu-3-temperature"],
        rule_refs=["quality:comfort-band:v2"],
        inference_trace_summary="Matched after-hours drift pattern from prior cases.",
    )
