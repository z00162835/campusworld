from __future__ import annotations

import hashlib
import math
from typing import Any, Dict, List, Optional, Sequence

from app.game_engine.agent_runtime.model_backends.protocols import ChatGenerativeResult


class StubQueryEmbeddingBackend:
    """Deterministic pseudo-embeddings from SHA256 digests (no torch)."""

    backend_kind = "stub_query_embedding"
    model_id = "stub-hash-embedding"

    def encode(self, texts: Sequence[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for t in texts:
            h = hashlib.sha256((t or "").encode("utf-8")).digest()
            vec = [((h[i] + h[i + 8]) / 510.0) - 0.5 for i in range(8)]
            out.append(vec)
        return out


class StubCrossEncoderRerankBackend:
    """Deterministic scalar scores from query/passage hashes."""

    backend_kind = "stub_cross_encoder"
    model_id = "stub-cross-encoder"

    def score_pairs(self, query: str, passages: Sequence[str]) -> List[float]:
        q = query or ""
        scores: List[float] = []
        for p in passages:
            raw = hashlib.sha256(f"{q}\n{p}".encode("utf-8")).digest()
            s = int.from_bytes(raw[:4], "big") / 0xFFFFFFFF
            scores.append(float(s))
        return scores


class StubChatGenerativeBackend:
    """Returns fixed JSON for tests or minimal valid slot JSON."""

    backend_kind = "stub_chat"
    model_id = "stub-chat"

    _EMPTY_SLOT = (
        '{"target_hint":null,"named_spans":[],"entities":[],"mandatory_tools":[]}'
    )

    def __init__(self, *, fixed_text: Optional[str] = None):
        self._fixed_text = fixed_text if fixed_text is not None else self._EMPTY_SLOT

    def complete_chat(
        self,
        messages: Sequence[Dict[str, Any]],
        *,
        max_new_tokens: int = 256,
        temperature: float = 0.0,
    ) -> ChatGenerativeResult:
        return ChatGenerativeResult(
            text=self._fixed_text,
            latency_ms=0.0,
            backend_kind=self.backend_kind,
            model_id=self.model_id,
        )


def cosine_sim(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
