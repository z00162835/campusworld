from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.game_engine.agent_runtime.model_backends.factories import (
    build_chat_generative_backend,
    build_cross_encoder_rerank_backend,
    build_query_embedding_backend,
)
from app.game_engine.agent_runtime.model_backends.stubs import cosine_sim
from app.game_engine.agent_runtime.tool_calling import ToolSchema
from app.game_engine.agent_runtime.tool_router.enrich_query import build_enrich_query_text
from app.game_engine.agent_runtime.tool_router.lexicon_store import lexicon_phrases_for_align, load_lexicon_entries
from app.game_engine.agent_runtime.tool_router.merge import dedupe_candidates
from app.game_engine.agent_runtime.tool_router.ner_gliner import extract_entity_spans_gliner
from app.game_engine.agent_runtime.tool_router.router_result import CandidateTier, RouterCandidate, RouterResult
from app.game_engine.agent_runtime.tool_router.rule_hints import apply_rules, direction_tokens
from app.game_engine.agent_runtime.tool_router.router_thresholds import (
    router_confidence_heuristic,
    router_should_clarify,
)
from app.game_engine.agent_runtime.tool_router.slot_filler import SlotFiller
from app.game_engine.agent_runtime.tool_router.tool_surface_revision import compute_tool_registry_revision
from app.game_engine.agent_runtime.tool_router.tool_router_config import ToolRouterConfig


def _tool_cards(schemas: Sequence[ToolSchema]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for s in schemas:
        name = getattr(s, "name", "") or ""
        desc = (getattr(s, "description", "") or "").strip()
        card = f"{name}\n{desc}".strip()
        out.append((name, card))
    return out


def _stub_router_backend_cfgs(extra: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    tr = {}
    if isinstance(extra, dict):
        inner = extra.get("tool_router")
        if isinstance(inner, dict):
            tr = inner
    emb = tr.get("embedding_backend") if isinstance(tr.get("embedding_backend"), dict) else {}
    ce = tr.get("cross_encoder_backend") if isinstance(tr.get("cross_encoder_backend"), dict) else {}
    chat = tr.get("slot_chat_backend") if isinstance(tr.get("slot_chat_backend"), dict) else {}
    return emb, ce, chat


def run_tool_router(
    *,
    cfg: ToolRouterConfig,
    user_message: str,
    world_snapshot: str,
    stm_snippet: Optional[str],
    intent_hint: Optional[Dict[str, Any]],
    tool_schemas: Sequence[ToolSchema],
    agent_extra: Optional[Dict[str, Any]] = None,
) -> Optional[RouterResult]:
    if not cfg.enabled:
        return None
    if not tool_schemas:
        return None

    registry_revision = compute_tool_registry_revision(tool_schemas)

    t0 = time.perf_counter()
    emb_cfg, ce_cfg, chat_cfg = _stub_router_backend_cfgs(agent_extra)
    embedder = build_query_embedding_backend(emb_cfg)
    reranker = build_cross_encoder_rerank_backend(ce_cfg)

    mandatory_rule, rule_hints, _rp_ver = apply_rules(user_message, rules_path=cfg.rules_path)
    dirs = direction_tokens(user_message)
    if dirs:
        rule_hints = [*rule_hints, f"movement_tokens:{','.join(dirs)}"]

    lex_id, lex_rows = load_lexicon_entries()
    phrases = lexicon_phrases_for_align(lex_rows)
    um_low = (user_message or "").casefold()
    lex_hits = [p for p in phrases if p.casefold() in um_low][:32]

    ner_labels = ("location", "organization", "person")
    ner_raw = extract_entity_spans_gliner(
        user_message,
        model_id=cfg.gliner_model_id,
        labels=ner_labels,
    )
    entity_spans: List[str] = []
    for span in ner_raw:
        if isinstance(span, dict):
            t = span.get("text")
            if isinstance(t, str) and t.strip():
                entity_spans.append(t.strip())

    enrich = build_enrich_query_text(
        user_message=user_message,
        world_snapshot=world_snapshot,
        stm_snippet=stm_snippet,
        rule_hints=rule_hints,
        entity_spans=entity_spans,
        lexicon_hits=lex_hits,
    )

    slot_mandatory: List[str] = []
    if cfg.slot_slm_enabled:
        slot_backend = build_chat_generative_backend(chat_cfg)
        filler = SlotFiller(slot_backend)
        _, slot_mandatory = filler.extract(user_message=user_message, enrich_query=enrich, repair=True)

    allowed_tool_names = frozenset(
        str(getattr(s, "name", "") or "").strip()
        for s in tool_schemas
        if getattr(s, "name", None)
    )
    mandatory = sorted((set(mandatory_rule) | set(slot_mandatory)) & allowed_tool_names)

    cards = _tool_cards(tool_schemas)
    names = [n for n, _ in cards]
    passages = [p for _, p in cards]
    raw_intent = str((intent_hint or {}).get("intent") or "").strip().lower()
    # Avoid substring false positives (e.g. "non_informational").
    k = cfg.k_info if raw_intent.split(".")[-1] == "informational" else cfg.k_default
    k = max(1, min(k, len(names)))

    q_emb = embedder.encode([enrich])[0]
    doc_embs = embedder.encode(passages)
    emb_scores = [cosine_sim(q_emb, d) for d in doc_embs]
    ranked_idx = sorted(range(len(names)), key=lambda i: emb_scores[i], reverse=True)
    top_idx = ranked_idx[:k]

    if cfg.stage_b_disabled:
        rerank_scores = [emb_scores[i] for i in top_idx]
    else:
        sub_passages = [passages[i] for i in top_idx]
        rerank_scores = reranker.score_pairs(enrich, sub_passages)

    candidates: List[RouterCandidate] = []
    for j, i in enumerate(top_idx):
        tier = CandidateTier.embedding if cfg.stage_b_disabled else CandidateTier.rerank
        sc = float(rerank_scores[j]) if j < len(rerank_scores) else float(emb_scores[i])
        candidates.append(RouterCandidate(tool_name=names[i], score=sc, tier=tier))

    for mn in mandatory_rule:
        if mn in names and mn not in {c.tool_name for c in candidates}:
            candidates.append(RouterCandidate(tool_name=mn, score=1.0, tier=CandidateTier.rule))

    candidates = dedupe_candidates(candidates)

    scores = [c.score for c in candidates]
    top = scores[0] if scores else 0.0
    second = scores[1] if len(scores) > 1 else 0.0
    margin = top - second
    confidence = router_confidence_heuristic(top, margin)
    clarify_flag = router_should_clarify(top, margin, cfg)

    parts = ["rule", "embedding"]
    if not cfg.stage_b_disabled:
        parts.append("rerank")
    if cfg.slot_slm_enabled:
        parts.append("slot")
    source = "+".join(parts) if parts else "stub"

    latency_ms = (time.perf_counter() - t0) * 1000.0
    return RouterResult(
        candidates=candidates,
        mandatory_tool_names=list(mandatory),
        suggested_tool_names=[],
        router_confidence=confidence,
        source=source,
        clarify=clarify_flag,  # True when below configured margin / top-score thresholds
        lexicon_active_id=lex_id,
        threshold_revision=cfg.threshold_revision,
        tool_registry_revision=registry_revision,
        latency_ms=latency_ms,
        enrich_query_text=enrich,
        enforcement_level=cfg.enforcement_level,
    )


def format_tool_router_hint(rr: RouterResult) -> str:
    lines = [
        "Tool router (pre-Plan):",
        f"  source: {rr.source}",
        f"  confidence: {rr.router_confidence:.4f}",
        f"  clarify: {rr.clarify} (True=suggest user/tool disambiguation)",
        f"  lexicon_active_id: {rr.lexicon_active_id or '(none)'}",
        f"  threshold_revision: {rr.threshold_revision or '(none)'}",
        f"  tool_registry_revision: {rr.tool_registry_revision or '(none)'}",
        f"  mandatory_tool_names: {rr.mandatory_tool_names}",
        "  top_candidates:",
    ]
    for c in rr.candidates[:12]:
        lines.append(f"    - {c.tool_name} score={c.score:.4f} tier={c.tier.value}")
    return "\n".join(lines)
