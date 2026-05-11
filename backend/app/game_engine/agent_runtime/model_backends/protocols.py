from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Protocol, Sequence

@dataclass
class ChatGenerativeResult:
    text: str
    latency_ms: float = 0.0
    backend_kind: str = 'stub'
    model_id: str = ''

class ChatGenerativeBackend(Protocol):

    def complete_chat(self, messages: Sequence[Dict[str, Any]], *, max_new_tokens: int=256, temperature: float=0.0) -> ChatGenerativeResult:
        ...

class QueryEmbeddingBackend(Protocol):

    def encode(self, texts: Sequence[str]) -> List[List[float]]:
        ...

class CrossEncoderRerankBackend(Protocol):

    def score_pairs(self, query: str, passages: Sequence[str]) -> List[float]:
        ...
