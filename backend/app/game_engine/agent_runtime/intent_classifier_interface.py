"""Shared intent-classifier interface for all agent runtimes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol


@dataclass(frozen=True)
class IntentClassification:
    intent: str
    confidence: float
    reason_tokens: List[str]
    source: str


class IntentClassifier(Protocol):
    def classify_intent(
        self,
        user_message: str,
        *,
        agent_id: Optional[str] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> IntentClassification:
        ...


class RuleFallbackIntentClassifier:
    """Fallback classifier used when model classifier is unavailable.

    Per plan decision R2=A: classification failures or uncertainty should default
    to informational.
    """

    def classify_intent(
        self,
        user_message: str,
        *,
        agent_id: Optional[str] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> IntentClassification:
        _ = agent_id
        _ = metadata
        text = (user_message or "").strip().lower()
        execute_patterns = (
            r"请执行",
            r"确认执行",
            r"继续执行",
            r"帮我创建",
            r"\bexecute\b",
            r"\bcreate\b",
        )
        verify_patterns = (
            r"是否存在",
            r"现在是什么状态",
            r"查一下",
            r"\bcurrent state\b",
            r"\bdoes it exist\b",
        )
        informational_patterns = (
            r"例子",
            r"怎么用",
            r"语法",
            r"\bhelp\b",
            r"\bexample\b",
            r"\busage\b",
        )
        reason_tokens: List[str] = []
        execute_hit = any(re.search(p, text, flags=re.IGNORECASE) for p in execute_patterns)
        verify_hit = any(re.search(p, text, flags=re.IGNORECASE) for p in verify_patterns)
        info_hit = any(re.search(p, text, flags=re.IGNORECASE) for p in informational_patterns)
        if execute_hit:
            reason_tokens.append("execute_cue")
        if verify_hit:
            reason_tokens.append("verify_state_cue")
        if info_hit:
            reason_tokens.append("informational_cue")
        has_confirmation = any(x in text for x in ("请执行", "确认执行", "继续执行", "yes, execute"))
        if execute_hit and has_confirmation:
            return IntentClassification(
                intent="execute",
                confidence=0.75,
                reason_tokens=reason_tokens,
                source="rule_fallback",
            )
        if verify_hit:
            return IntentClassification(
                intent="verify_state",
                confidence=0.70,
                reason_tokens=reason_tokens,
                source="rule_fallback",
            )
        if execute_hit and not has_confirmation:
            reason_tokens.append("execute_without_confirmation_downgraded")
        return IntentClassification(
            intent="informational",
            confidence=0.65,
            reason_tokens=reason_tokens,
            source="rule_fallback",
        )


def classify_intent(
    user_message: str,
    *,
    agent_id: Optional[str] = None,
    metadata: Optional[Dict[str, object]] = None,
    classifier: Optional[IntentClassifier] = None,
) -> IntentClassification:
    cls = classifier or RuleFallbackIntentClassifier()
    try:
        out = cls.classify_intent(user_message, agent_id=agent_id, metadata=metadata)
        if out.intent in {"informational", "verify_state", "execute"}:
            return out
    except Exception:
        pass
    # R2=A: default informational on classifier failure.
    return IntentClassification(
        intent="informational",
        confidence=0.0,
        reason_tokens=["classifier_failure_default_informational"],
        source="fallback_default",
    )

