"""Long-term memory semantic search (pgvector) and LTM–LTM link expansion.

Schema and behavior contracts live under ``docs/models/SPEC/features/``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.system import AgentLongTermMemory, AgentLongTermMemoryLink

EMBEDDING_DIM = 1536


def search_ltm_by_embedding(
    session: Session,
    agent_node_id: int,
    query_vector: Sequence[float],
    *,
    k: int = 8,
    embedding_model: Optional[str] = None,
) -> List[Tuple[int, str, float]]:
    """
    Cosine-distance KNN within one agent's LTM rows that have embeddings.

    Returns list of (ltm_id, summary, distance) ordered by ascending distance.
    """
    qv = list(query_vector)
    if len(qv) != EMBEDDING_DIM:
        raise ValueError(f"query_vector must have length {EMBEDDING_DIM}, got {len(qv)}")

    vec_literal = "[" + ",".join(str(float(x)) for x in qv) + "]"
    sql = """
    SELECT id, summary, (embedding <=> (:qv)::vector) AS dist
    FROM agent_long_term_memory
    WHERE agent_node_id = :aid AND embedding IS NOT NULL
    """
    params: Dict[str, Any] = {"aid": agent_node_id, "qv": vec_literal, "k": k}
    if embedding_model is not None:
        sql += " AND embedding_model = :em"
        params["em"] = embedding_model
    sql += " ORDER BY embedding <=> (:qv)::vector ASC LIMIT :k"

    rows = session.execute(text(sql), params).fetchall()
    return [(int(r[0]), str(r[1] or ""), float(r[2])) for r in rows]


def expand_ltm_linked_neighbors(
    session: Session,
    agent_node_id: int,
    seed_ltm_ids: Sequence[int],
    *,
    max_depth: int = 2,
) -> Set[int]:
    """
    Undirected BFS over agent_long_term_memory_links (both directions), scoped by agent_node_id.
    Includes all seed ids. Stops cycles via visited set.
    """
    seeds = [int(x) for x in seed_ltm_ids]
    visited: Set[int] = set(seeds)
    frontier: List[int] = list(seeds)
    for _ in range(max_depth):
        if not frontier:
            break
        next_frontier: List[int] = []
        for fid in frontier:
            q = text(
                """
                SELECT target_ltm_id AS tid FROM agent_long_term_memory_links
                WHERE agent_node_id = :a AND source_ltm_id = :s
                UNION
                SELECT source_ltm_id AS tid FROM agent_long_term_memory_links
                WHERE agent_node_id = :a AND target_ltm_id = :s
                """
            )
            for (tid,) in session.execute(q, {"a": agent_node_id, "s": fid}).fetchall():
                tid = int(tid)
                if tid not in visited:
                    visited.add(tid)
                    next_frontier.append(tid)
        frontier = next_frontier
    return visited


def _ltm_belongs_to_agent(session: Session, ltm_id: int, agent_node_id: int) -> bool:
    row = (
        session.query(AgentLongTermMemory.id)
        .filter(
            AgentLongTermMemory.id == ltm_id,
            AgentLongTermMemory.agent_node_id == agent_node_id,
        )
        .first()
    )
    return row is not None


def create_ltm_link(
    session: Session,
    *,
    agent_node_id: int,
    source_ltm_id: int,
    target_ltm_id: int,
    link_type: str,
    weight: float = 1.0,
    payload: Optional[Dict[str, Any]] = None,
) -> AgentLongTermMemoryLink:
    """Insert a link after validating both LTM rows belong to the same agent."""
    if source_ltm_id == target_ltm_id:
        raise ValueError("source_ltm_id and target_ltm_id must differ")
    if not _ltm_belongs_to_agent(session, source_ltm_id, agent_node_id):
        raise ValueError("source LTM does not belong to agent")
    if not _ltm_belongs_to_agent(session, target_ltm_id, agent_node_id):
        raise ValueError("target LTM does not belong to agent")
    row = AgentLongTermMemoryLink(
        agent_node_id=agent_node_id,
        source_ltm_id=source_ltm_id,
        target_ltm_id=target_ltm_id,
        link_type=link_type,
        weight=weight,
        payload=payload or {},
    )
    session.add(row)
    session.flush()
    return row


def set_ltm_embedding(
    session: Session,
    ltm_id: int,
    agent_node_id: int,
    embedding: Sequence[float],
    *,
    embedding_model: str,
) -> None:
    """Set embedding on an LTM row (caller responsible for dimension)."""
    from datetime import datetime, timezone

    ev = list(embedding)
    if len(ev) != EMBEDDING_DIM:
        raise ValueError(f"embedding must have length {EMBEDDING_DIM}")
    n = (
        session.query(AgentLongTermMemory)
        .filter(
            AgentLongTermMemory.id == ltm_id,
            AgentLongTermMemory.agent_node_id == agent_node_id,
        )
        .first()
    )
    if n is None:
        raise ValueError("LTM row not found for agent")
    n.embedding = ev
    n.embedding_model = embedding_model
    n.embedding_updated_at = datetime.now(timezone.utc)
    session.flush()


def build_ltm_memory_context_for_tick(
    session: Session,
    agent_node_id: int,
    *,
    user_message: str,
    limit: int = 8,
    max_chars: int = 2000,
) -> Optional[str]:
    """
    Concatenate recent LTM row summaries for optional NLP memory_context injection.

    Newest rows first. Does not require embeddings; semantic KNN via
    search_ltm_by_embedding can be added when a query embedding pipeline exists.
    user_message is reserved for future relevance ranking.
    """
    _ = user_message
    rows = (
        session.query(AgentLongTermMemory)
        .filter(AgentLongTermMemory.agent_node_id == agent_node_id)
        .order_by(AgentLongTermMemory.id.desc())
        .limit(limit)
        .all()
    )
    parts: List[str] = []
    for r in rows:
        s = str(r.summary or "").strip()
        if s:
            parts.append(s)
    if not parts:
        return None
    text = "\n".join(parts)
    if len(text) > max_chars:
        text = text[: max_chars - 3] + "..."
    return text
