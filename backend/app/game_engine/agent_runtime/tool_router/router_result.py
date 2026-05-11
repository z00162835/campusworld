from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

class CandidateTier(str, Enum):
    """Last-hop source for a candidate (not equal to pipeline-level ``source`` string)."""
    rule = 'rule'
    embedding = 'embedding'
    rerank = 'rerank'
    slm = 'slm'

class EnforcementLevel(str, Enum):
    hint_only = 'hint_only'
    schema_subset = 'schema_subset'
    hard_must_invoke = 'hard_must_invoke'

@dataclass
class RouterCandidate:
    tool_name: str
    score: float
    tier: CandidateTier

@dataclass
class RouterResult:
    candidates: List[RouterCandidate]
    mandatory_tool_names: List[str]
    suggested_tool_names: List[str] = field(default_factory=list)
    router_confidence: float = 0.0
    source: str = ''
    clarify: Optional[bool] = None
    lexicon_active_id: Optional[str] = None
    threshold_revision: str = ''
    tool_registry_revision: str = ''
    latency_ms: float = 0.0
    enrich_query_text: str = ''
    enforcement_level: EnforcementLevel = EnforcementLevel.hint_only

    def schema_allowlist_names(self) -> List[str]:
        """Union of candidate tools and mandatory (strict schema_subset formula)."""
        names: Set[str] = set()
        for c in self.candidates:
            names.add(c.tool_name)
        for m in self.mandatory_tool_names:
            names.add(m)
        return sorted(names)

    def to_payload_dict(self) -> Dict[str, Any]:
        return {'candidates': [{'tool_name': c.tool_name, 'score': c.score, 'tier': c.tier.value} for c in self.candidates], 'mandatory_tool_names': list(self.mandatory_tool_names), 'suggested_tool_names': list(self.suggested_tool_names), 'router_confidence': self.router_confidence, 'source': self.source, 'clarify': self.clarify, 'lexicon_active_id': self.lexicon_active_id, 'threshold_revision': self.threshold_revision, 'tool_registry_revision': self.tool_registry_revision, 'latency_ms': self.latency_ms, 'enforcement_level': self.enforcement_level.value}

    def to_trace_dict(self) -> Dict[str, Any]:
        return {'tool_router_source': self.source, 'tool_router_confidence': self.router_confidence, 'tool_router_clarify': self.clarify, 'tool_router_lexicon_active_id': self.lexicon_active_id, 'tool_router_threshold_revision': self.threshold_revision, 'tool_router_registry_revision': self.tool_registry_revision, 'tool_router_latency_ms': round(self.latency_ms, 3), 'tool_router_enforcement': self.enforcement_level.value, 'tool_router_mandatory': list(self.mandatory_tool_names), 'tool_router_top_candidates': [c.tool_name for c in self.candidates[:8]]}
