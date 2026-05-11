from __future__ import annotations
from typing import Any, Dict, Optional
from app.game_engine.agent_runtime.model_backends.protocols import ChatGenerativeBackend, CrossEncoderRerankBackend, QueryEmbeddingBackend
from app.game_engine.agent_runtime.model_backends.stubs import StubChatGenerativeBackend, StubCrossEncoderRerankBackend, StubQueryEmbeddingBackend

def build_query_embedding_backend(cfg: Optional[Dict[str, Any]]) -> QueryEmbeddingBackend:
    if not isinstance(cfg, dict):
        return StubQueryEmbeddingBackend()
    kind = str(cfg.get('kind') or 'stub').lower().strip()
    if kind == 'stub':
        return StubQueryEmbeddingBackend()
    return StubQueryEmbeddingBackend()

def build_cross_encoder_rerank_backend(cfg: Optional[Dict[str, Any]]) -> CrossEncoderRerankBackend:
    if not isinstance(cfg, dict):
        return StubCrossEncoderRerankBackend()
    kind = str(cfg.get('kind') or 'stub').lower().strip()
    if kind == 'stub':
        return StubCrossEncoderRerankBackend()
    return StubCrossEncoderRerankBackend()

def build_chat_generative_backend(cfg: Optional[Dict[str, Any]]) -> ChatGenerativeBackend:
    if not isinstance(cfg, dict):
        return StubChatGenerativeBackend()
    kind = str(cfg.get('kind') or 'stub').lower().strip()
    if kind == 'stub':
        fixed = cfg.get('fixed_text')
        if isinstance(fixed, str):
            return StubChatGenerativeBackend(fixed_text=fixed)
        return StubChatGenerativeBackend()
    return StubChatGenerativeBackend()
