from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class AgentLoopConfig:
    min_complete_chars: int = 80
    deferral_patterns: Optional[List[str]] = None

    @classmethod
    def from_agent_extra(cls, extra: Optional[Dict[str, Any]]) -> 'AgentLoopConfig':
        raw = extra if isinstance(extra, dict) else {}
        min_chars = raw.get('agent_loop_min_complete_chars', 80)
        try:
            min_chars_i = max(0, int(min_chars))
        except (TypeError, ValueError):
            min_chars_i = 80
        patterns_raw = raw.get('agent_loop_deferral_patterns')
        patterns: Optional[List[str]] = None
        if isinstance(patterns_raw, list) and patterns_raw:
            patterns = [str(p) for p in patterns_raw if str(p).strip()]
        return cls(min_complete_chars=min_chars_i, deferral_patterns=patterns)
