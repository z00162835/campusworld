"""B5: decision → runtime_action derivation mapping tests.

Locks the v1 mapping table (F16 §3.2 / F18 §3.4): each ``decision`` derives a
specific ``runtime_action``, and runtime consumers use ``is_block``/``is_allow``
rather than reading ``decision``/``runtime_action`` directly.
"""
from __future__ import annotations

from app.game_engine.agent_runtime.policy import PolicyDecision


class TestPolicyDecisionMapping:
    def test_allow_maps_to_pass(self):
        d = PolicyDecision.allow("cp", reason_code="ok")
        assert d.decision == "allow"
        assert d.runtime_action == "pass"
        assert d.is_allow is True
        assert d.is_block is False

    def test_deny_maps_to_block(self):
        d = PolicyDecision.deny("cp", "reason")
        assert d.decision == "deny"
        assert d.runtime_action == "block"
        assert d.is_block is True
        assert d.is_allow is False

    def test_require_approval_maps_to_block_v1(self):
        d = PolicyDecision.require_approval("cp", "reason")
        assert d.decision == "require_approval"
        assert d.runtime_action == "block"
        assert d.is_block is True

    def test_f18_fail_maps_to_block(self):
        d = PolicyDecision(
            decision="fail",
            reason_code="max_iterations",
            check_point="after_state_execute",
            runtime_action="block",
        )
        assert d.is_block is True
        assert d.is_allow is False

    def test_f18_final_success_maps_to_pass(self):
        d = PolicyDecision(
            decision="final_success",
            reason_code="complete",
            check_point="before_terminal",
            runtime_action="pass",
        )
        assert d.is_allow is True
        assert d.is_block is False

    def test_f18_continue_maps_to_pass(self):
        d = PolicyDecision(
            decision="continue",
            reason_code="ok",
            check_point="after_state_execute",
            runtime_action="pass",
        )
        assert d.is_allow is True

    def test_f18_replan_maps_to_pass(self):
        """replan does not block; the event drives the transition."""
        d = PolicyDecision(
            decision="replan",
            reason_code="check_retry",
            check_point="after_state_execute",
            runtime_action="pass",
        )
        assert d.is_allow is True
        assert d.is_block is False

    def test_f18_pause_maps_to_pause(self):
        d = PolicyDecision(
            decision="pause",
            reason_code="clarify",
            check_point="after_state_execute",
            runtime_action="pause",
        )
        assert d.is_block is False
        assert d.is_allow is False
        assert d.runtime_action == "pause"

    def test_runtime_consumers_use_is_block_is_allow(self):
        """The contract: consumers check is_block/is_allow, not decision directly."""
        allow = PolicyDecision.allow("cp")
        deny = PolicyDecision.deny("cp", "r")
        fail = PolicyDecision("fail", "r", "cp", "block")
        replan = PolicyDecision("replan", "r", "cp", "pass")
        assert allow.is_allow and not allow.is_block
        assert not deny.is_allow and deny.is_block
        assert not fail.is_allow and fail.is_block
        assert replan.is_allow and not replan.is_block

    def test_allow_with_transform_is_allow(self):
        """G10: allow_with_transform is an 'allow' decision (transform is non-blocking)."""
        d = PolicyDecision(
            decision="allow_with_transform",
            reason_code="redact",
            check_point="before_final_answer",
            runtime_action="transform",
        )
        assert d.is_allow is True
        assert d.is_block is False


class TestF18Factories:
    """G13: F18 decision factories internalize the B5 mapping."""

    def test_fail_factory(self):
        d = PolicyDecision.fail("after_state_execute", "max_iterations")
        assert d.decision == "fail"
        assert d.runtime_action == "block"
        assert d.is_block is True

    def test_fail_factory_with_degraded_action(self):
        d = PolicyDecision.fail("cp", "r", degraded_action="block")
        assert d.degraded_action == "block"

    def test_pause_factory(self):
        d = PolicyDecision.pause("cp", "clarify", degraded_action="clarify")
        assert d.decision == "pause"
        assert d.runtime_action == "pause"
        assert d.degraded_action == "clarify"
        assert d.is_block is False
        assert d.is_allow is False

    def test_final_success_factory(self):
        d = PolicyDecision.final_success("before_terminal")
        assert d.decision == "final_success"
        assert d.runtime_action == "pass"
        assert d.is_allow is True

    def test_final_success_factory_with_quality_score(self):
        score = {"surface": 1.0, "process": 1.0, "semantic": 0.9}
        d = PolicyDecision.final_success("before_terminal", quality_score=score)
        assert d.quality_score == score

    def test_replan_factory(self):
        d = PolicyDecision.replan("after_state_execute", "check_retry")
        assert d.decision == "replan"
        assert d.runtime_action == "pass"
        assert d.is_allow is True
        assert d.is_block is False

    def test_continue_factory(self):
        d = PolicyDecision.continue_("after_state_execute")
        assert d.decision == "continue"
        assert d.runtime_action == "pass"
        assert d.is_allow is True
