"""B5: _prepare_skill_context trace serialization uses real PolicyDecision.

The trace row for a blocked skill must serialize the actual PolicyDecision
(decision / runtime_action / reason_code / evidence) via the
``execution_gate._policy_decision_to_trace`` helper, not hardcode
``'decision':'deny'`` / ``'runtime_action':'block'``.
"""
from __future__ import annotations

from app.game_engine.agent_runtime.execution_gate import _policy_decision_to_trace
from app.game_engine.agent_runtime.policy import PolicyDecision


class TestPrepareSkillContextTrace:
    def test_helper_serializes_real_decision(self):
        d = PolicyDecision.deny(
            "before_skill_activation",
            "policy_blocked_skill_activation_mode",
            evidence={"skill_id": "problem_framing", "activation_mode": "blocked"},
        )
        row = _policy_decision_to_trace(d)
        assert row["step"] == "policy_decision"
        assert row["check_point"] == "before_skill_activation"
        assert row["decision"] == "deny"
        assert row["runtime_action"] == "block"
        assert row["reason_code"] == "policy_blocked_skill_activation_mode"
        assert row["evidence"]["skill_id"] == "problem_framing"

    def test_helper_serializes_require_approval_not_hardcoded_deny(self):
        """A require_approval decision must serialize as require_approval, not deny."""
        d = PolicyDecision.require_approval(
            "before_tool_call",
            "policy_blocked_side_effect_write_high",
            evidence={"side_effect_level": "write_high"},
        )
        row = _policy_decision_to_trace(d)
        assert row["decision"] == "require_approval"
        assert row["runtime_action"] == "block"
        assert row["decision"] != "deny"

    def test_helper_preserves_evidence_detector_field(self):
        d = PolicyDecision.deny("cp", "r", evidence={"detector": "side_effect_level_detector"})
        row = _policy_decision_to_trace(d)
        assert row["evidence"]["detector"] == "side_effect_level_detector"

    def test_llm_pdca_uses_helper_not_hardcoded(self):
        """The _prepare_skill_context code path imports and calls the helper."""
        import inspect

        from app.game_engine.agent_runtime.frameworks import llm_pdca

        source = inspect.getsource(llm_pdca.LlmPDCAFramework._prepare_skill_context)
        assert "_policy_decision_to_trace" in source
