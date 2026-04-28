"""Phase B PR3: BLOCKED_BY cycle detection (F01 §2.1)."""

from __future__ import annotations

import pytest

from app.services.task.blocked_by import (
    detect_blocked_by_cycle,
    detect_blocked_by_cycle_in_memory,
)


# ---------------------------------------------------------------------------
# Pure in-memory variant (deterministic, no DB)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_self_loop_is_cycle():
    assert detect_blocked_by_cycle_in_memory([], from_id=1, to_id=1)


@pytest.mark.unit
def test_two_disjoint_chains_no_cycle():
    edges = [(1, 2), (2, 3), (10, 11), (11, 12)]
    assert not detect_blocked_by_cycle_in_memory(edges, from_id=3, to_id=4)


@pytest.mark.unit
def test_classic_three_node_cycle_detected():
    """Adding (A->B) when B->C->A already exists must report cycle."""
    edges = [(2, 3), (3, 1)]  # B->C, C->A
    # Proposing A->B (1->2) closes cycle through 2->3->1
    assert detect_blocked_by_cycle_in_memory(edges, from_id=1, to_id=2)


@pytest.mark.unit
def test_long_chain_no_cycle_when_acyclic():
    edges = [(i, i + 1) for i in range(1, 60)]
    assert not detect_blocked_by_cycle_in_memory(edges, from_id=60, to_id=61)


@pytest.mark.unit
def test_depth_safety_net_triggers_at_max_depth():
    """A pathological forward-only chain longer than max_depth is conservatively reported."""
    edges = [(i, i + 1) for i in range(1, 200)]
    # Adding (200, 1) — full graph traversal would say "cycle".
    assert detect_blocked_by_cycle_in_memory(edges, from_id=200, to_id=1, max_depth=64)


@pytest.mark.unit
def test_diamond_no_cycle():
    # A -> B, A -> C, B -> D, C -> D
    edges = [(1, 2), (1, 3), (2, 4), (3, 4)]
    assert not detect_blocked_by_cycle_in_memory(edges, from_id=4, to_id=5)


# ---------------------------------------------------------------------------
# SQL variant: drive with a tiny stub session that mimics SQLAlchemy
# ---------------------------------------------------------------------------


class _StubResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _StubSession:
    def __init__(self, *, returns):
        self._returns = returns
        self.last_params: dict | None = None

    def execute(self, _stmt, params):
        self.last_params = params
        return _StubResult(self._returns)


@pytest.mark.unit
def test_self_loop_short_circuits_without_query():
    sess = _StubSession(returns=[(1,)])
    assert detect_blocked_by_cycle(sess, from_id=7, to_id=7)
    assert sess.last_params is None  # no query issued


@pytest.mark.unit
def test_no_path_returns_false():
    sess = _StubSession(returns=[])
    assert not detect_blocked_by_cycle(sess, from_id=1, to_id=2)
    assert sess.last_params == {"seed_id": 2, "probe_id": 1, "max_depth": 64}


@pytest.mark.unit
def test_path_exists_returns_true():
    sess = _StubSession(returns=[(1,)])
    assert detect_blocked_by_cycle(sess, from_id=1, to_id=2)
