from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DraftCompletenessVerdict(str, Enum):
    complete = 'complete'
    retry_loop = 'retry_loop'
    fail_fallback = 'fail_fallback'


@dataclass(frozen=True)
class PendingToolWork:
    reason_codes: List[str]
    dropped_names: List[str] = field(default_factory=list)
    finish_reason: Optional[str] = None


@dataclass(frozen=True)
class DraftReasonContext:
    intent_hint: Optional[Dict[str, Any]] = None
