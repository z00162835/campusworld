"""PolicyDecision — outcome of a single check-point evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

DecisionType = Literal[
    "deny", "allow", "require_approval", "allow_with_transform",
    # F18 quality/stop extensions (audit/trace in v1; driver wiring post-v1).
    "fail", "pause", "final_success", "replan", "continue",
]
RuntimeAction = Literal["block", "pause", "transform", "block_and_rewrite", "pass"]


@dataclass(frozen=True)
class PolicyDecision:
    decision: DecisionType
    reason_code: str
    check_point: str
    runtime_action: RuntimeAction
    transform_applied: Optional[Dict[str, Any]] = None
    evidence: Optional[Dict[str, Any]] = None
    # F18 extensions (optional, backward-compatible).
    quality_score: Optional[Dict[str, float]] = None  # layered sub-scores {surface, process, semantic}
    degraded_action: Optional[str] = None  # pause→block/clarify records the degraded action

    @property
    def is_allow(self) -> bool:
        # "passes through" — no blocking intervention. Covers:
        # - allow (runtime_action="pass")
        # - allow_with_transform (runtime_action="transform") — still an "allow" decision
        # - F18 final_success / continue / replan (runtime_action="pass")
        # replan's transition is driven by event, not by blocking.
        return self.runtime_action in ("pass", "transform")

    @property
    def is_block(self) -> bool:
        return self.runtime_action in ("block", "block_and_rewrite")

    # --- F16 base factories -------------------------------------------------

    @classmethod
    def allow(cls, check_point: str, reason_code: str = "policy_pass") -> "PolicyDecision":
        return cls(
            decision="allow",
            reason_code=reason_code,
            check_point=check_point,
            runtime_action="pass",
        )

    @classmethod
    def deny(
        cls,
        check_point: str,
        reason_code: str,
        *,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> "PolicyDecision":
        return cls(
            decision="deny",
            reason_code=reason_code,
            check_point=check_point,
            runtime_action="block",
            evidence=evidence,
        )

    @classmethod
    def require_approval(
        cls,
        check_point: str,
        reason_code: str,
        *,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> "PolicyDecision":
        # v1: require_approval degrades to synchronous block.
        return cls(
            decision="require_approval",
            reason_code=reason_code,
            check_point=check_point,
            runtime_action="block",
            evidence=evidence,
        )

    # --- F18 quality/stop factories (B5 mapping internalized) --------------

    @classmethod
    def fail(
        cls,
        check_point: str,
        reason_code: str,
        *,
        evidence: Optional[Dict[str, Any]] = None,
        degraded_action: Optional[str] = None,
    ) -> "PolicyDecision":
        # B5: fail → block (unrecoverable terminal).
        return cls(
            decision="fail",
            reason_code=reason_code,
            check_point=check_point,
            runtime_action="block",
            evidence=evidence,
            degraded_action=degraded_action,
        )

    @classmethod
    def pause(
        cls,
        check_point: str,
        reason_code: str,
        *,
        degraded_action: str,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> "PolicyDecision":
        # B5: pause → pause (v1 degraded_action overrides to block/clarify at consumer).
        return cls(
            decision="pause",
            reason_code=reason_code,
            check_point=check_point,
            runtime_action="pause",
            evidence=evidence,
            degraded_action=degraded_action,
        )

    @classmethod
    def final_success(
        cls,
        check_point: str,
        reason_code: str = "final_success",
        *,
        evidence: Optional[Dict[str, Any]] = None,
        quality_score: Optional[Dict[str, float]] = None,
    ) -> "PolicyDecision":
        # B5: final_success → pass.
        return cls(
            decision="final_success",
            reason_code=reason_code,
            check_point=check_point,
            runtime_action="pass",
            evidence=evidence,
            quality_score=quality_score,
        )

    @classmethod
    def replan(
        cls,
        check_point: str,
        reason_code: str,
        *,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> "PolicyDecision":
        # B5: replan → pass (transition driven by event, not by blocking).
        return cls(
            decision="replan",
            reason_code=reason_code,
            check_point=check_point,
            runtime_action="pass",
            evidence=evidence,
        )

    @classmethod
    def continue_(cls, check_point: str, reason_code: str = "continue") -> "PolicyDecision":
        # B5: continue → pass. (Method named continue_ — `continue` is a Python keyword.)
        return cls(
            decision="continue",
            reason_code=reason_code,
            check_point=check_point,
            runtime_action="pass",
        )
