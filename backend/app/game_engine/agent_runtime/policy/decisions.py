"""PolicyDecision — outcome of a single check-point evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

DecisionType = Literal["deny", "allow", "require_approval", "allow_with_transform"]
RuntimeAction = Literal["block", "pause", "transform", "block_and_rewrite", "pass"]


@dataclass(frozen=True)
class PolicyDecision:
    decision: DecisionType
    reason_code: str
    check_point: str
    runtime_action: RuntimeAction
    transform_applied: Optional[Dict[str, Any]] = None
    evidence: Optional[Dict[str, Any]] = None

    @property
    def is_allow(self) -> bool:
        return self.decision == "allow" and self.runtime_action == "pass"

    @property
    def is_block(self) -> bool:
        return self.runtime_action in ("block", "block_and_rewrite")

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
        # v1: require_approval degrades to synchronous block (D8).
        return cls(
            decision="require_approval",
            reason_code=reason_code,
            check_point=check_point,
            runtime_action="block",
            evidence=evidence,
        )
