"""BLOCKED_BY cycle detection (Phase B PR3).

SSOT: ``docs/task/SPEC/features/F01_TASK_ONTOLOGY_AND_NODE_TYPES.md §2.1``.

Pure function over a SQLAlchemy ``Session``-like object — the test suite
substitutes a fake driver, so we treat the session as duck-typed (only
``execute()`` is called). The recursive CTE is hard-capped at depth 64
both at the SQL level (``WHERE depth < 64``) and at the Python level
(safety net for stub drivers).
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence


_MAX_DEPTH = 64

_CYCLE_SQL = """
WITH RECURSIVE closure(source, depth) AS (
    SELECT target_id AS source, 1 AS depth
      FROM relationships
     WHERE source_id = :seed_id
       AND type_code = 'BLOCKED_BY'
       AND is_active = TRUE
    UNION
    SELECT r.target_id, c.depth + 1
      FROM relationships r
      JOIN closure c ON c.source = r.source_id
     WHERE r.type_code = 'BLOCKED_BY'
       AND r.is_active = TRUE
       AND c.depth < :max_depth
)
SELECT 1 FROM closure WHERE source = :probe_id LIMIT 1;
"""


def detect_blocked_by_cycle(session: Any, *, from_id: int, to_id: int) -> bool:
    """Return ``True`` if creating ``BLOCKED_BY(from_id -> to_id)`` would close a cycle.

    Self-loops (``from_id == to_id``) are always reported as cycles.
    Depth is capped at 64 (SPEC §2.1 兜底).
    """
    if int(from_id) == int(to_id):
        return True

    from sqlalchemy import text

    result = session.execute(
        text(_CYCLE_SQL),
        {"seed_id": int(to_id), "probe_id": int(from_id), "max_depth": _MAX_DEPTH},
    )
    row = result.first()
    return row is not None


def detect_blocked_by_cycle_in_memory(
    edges: Iterable[Sequence[int]],
    *,
    from_id: int,
    to_id: int,
    max_depth: int = _MAX_DEPTH,
) -> bool:
    """Pure in-memory variant for unit tests and offline data-repair tools.

    ``edges`` is an iterable of ``(source_id, target_id)`` BLOCKED_BY pairs.
    """
    if int(from_id) == int(to_id):
        return True

    out: dict[int, list[int]] = {}
    for s, t in edges:
        out.setdefault(int(s), []).append(int(t))

    # BFS from `to_id`; if we reach `from_id` within max_depth, the new edge
    # (from_id -> to_id) closes the cycle.
    frontier = [(int(to_id), 0)]
    visited = {int(to_id)}
    while frontier:
        node, depth = frontier.pop(0)
        if depth >= max_depth:
            return True  # pathological depth → conservative cycle report
        for nxt in out.get(node, ()):
            if nxt == int(from_id):
                return True
            if nxt in visited:
                continue
            visited.add(nxt)
            frontier.append((nxt, depth + 1))
    return False


__all__ = [
    "detect_blocked_by_cycle",
    "detect_blocked_by_cycle_in_memory",
]
