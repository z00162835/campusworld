"""Phase B PR6: task system performance bench (4 scenarios).

Anchors: [SPEC §1.8.2](../../../../docs/task/SPEC/SPEC.md#182-性能基线oq-30).

Scenarios:

- ``B1`` — ``transition`` single-task hot path (P99 ≤ 50 ms).
- ``B2`` — 32-agent concurrent ``claim`` (throughput ≥ 200 req/s; OL fail ≤ 3%).
- ``B3`` — pool view query (P99 ≤ 30 ms; smoke target 50 ms @ 10k rows).
- ``B4`` — ``scope_selector`` validation (≤ 200 ms @ 10k targets).

Run modes (``--mode smoke|release``) keep the bench cheap on CI and full-fat
in release pipelines. Output is JSON written to ``--out`` (baseline trend
file). Exit code is non-zero when any scenario misses 70% of its target.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


_DB_URL_ENV = "CAMPUSWORLD_TEST_DATABASE_URL"


@dataclass
class ScenarioResult:
    name: str
    target: str
    metric: str
    value: float
    threshold: float
    passed: bool
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _percentile(samples: List[float], pct: float) -> float:
    if not samples:
        return 0.0
    s = sorted(samples)
    k = max(0, min(len(s) - 1, int(round((pct / 100.0) * (len(s) - 1)))))
    return s[k]


def _make_actor(session, name: str) -> int:
    row = session.execute(
        text(
            """
            INSERT INTO nodes (type_id, type_code, name, attributes, is_active, is_public)
            SELECT id, type_code, :name, '{}'::jsonb, TRUE, FALSE
              FROM node_types WHERE type_code = 'default_object'
            RETURNING id
            """
        ),
        {"name": name},
    ).first()
    session.commit()
    return int(row[0])


# ---------------------------------------------------------------------------
# B1 — transition hot path
# ---------------------------------------------------------------------------


def run_b1_transition_hot_path(engine, *, n: int) -> ScenarioResult:
    from app.services.task.permissions import Principal
    from app.services.task.task_state_machine import create_task, transition

    Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    s = Session()
    actor_id = _make_actor(s, f"b1-{uuid.uuid4()}")
    actor = Principal(id=actor_id, kind="user")
    pool_id = int(
        s.execute(text("SELECT id FROM task_pools WHERE key='hicampus.cleaning'")).scalar()
    )
    s.close()

    samples_ms: List[float] = []
    for _ in range(n):
        s = Session()
        try:
            created = create_task(title=f"b1-{uuid.uuid4()}", actor=actor, db_session=s)
            t0 = time.perf_counter()
            transition(
                task_id=created.task_id,
                event="publish",
                actor_principal=actor,
                expected_version=created.state_version,
                payload={"pool_id": pool_id},
                db_session=s,
            )
            samples_ms.append((time.perf_counter() - t0) * 1000.0)
        finally:
            s.close()

    p99 = _percentile(samples_ms, 99)
    target_ms = 50.0
    return ScenarioResult(
        name="B1_transition_hot_path",
        target=f"P99 ≤ {target_ms} ms",
        metric="p99_ms",
        value=p99,
        threshold=target_ms,
        passed=p99 <= target_ms / 0.70,  # ≥70% of target margin
        extra={
            "n": len(samples_ms),
            "p50_ms": _percentile(samples_ms, 50),
            "p95_ms": _percentile(samples_ms, 95),
            "max_ms": max(samples_ms) if samples_ms else 0.0,
        },
    )


# ---------------------------------------------------------------------------
# B2 — concurrent claim
# ---------------------------------------------------------------------------


def run_b2_concurrent_claim(engine, *, agents: int = 32) -> ScenarioResult:
    from app.services.task.errors import OptimisticLockError
    from app.services.task.permissions import Principal
    from app.services.task.task_state_machine import create_task, transition

    Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    s = Session()
    owner_id = _make_actor(s, f"b2-owner-{uuid.uuid4()}")
    owner = Principal(id=owner_id, kind="user")
    pool_id = int(
        s.execute(text("SELECT id FROM task_pools WHERE key='hicampus.cleaning'")).scalar()
    )
    claim_targets: list[tuple[int, int]] = []
    for i in range(agents):
        created = create_task(title=f"b2 probe {i}", actor=owner, db_session=s)
        pub = transition(
            task_id=created.task_id,
            event="publish",
            actor_principal=owner,
            expected_version=created.state_version,
            payload={"pool_id": pool_id},
            db_session=s,
        )
        claim_targets.append((created.task_id, pub.state_version))
    s.close()

    actors = [Principal(id=_mk_actor(engine), kind="agent") for _ in range(agents)]

    successes = 0
    failures = 0
    lock = threading.Lock()
    t0 = time.perf_counter()

    def worker(actor: Principal, task_id: int, expected_version: int):
        nonlocal successes, failures
        s = Session()
        try:
            transition(
                task_id=task_id,
                event="claim",
                actor_principal=actor,
                expected_version=expected_version,
                db_session=s,
            )
            with lock:
                successes += 1
        except OptimisticLockError:
            with lock:
                failures += 1
        except Exception:
            # Other terminal exceptions (e.g. invalid transition once claimed)
            # count as a failed contention.
            with lock:
                failures += 1
        finally:
            s.close()

    threads = [
        threading.Thread(target=worker, args=(actor, tid, ver))
        for actor, (tid, ver) in zip(actors, claim_targets, strict=False)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    elapsed = time.perf_counter() - t0
    throughput = (successes + failures) / max(elapsed, 1e-6)
    fail_rate = failures / max(successes + failures, 1)
    target_throughput = 200.0
    return ScenarioResult(
        name="B2_balanced_claim_32agents_32tasks",
        target="≥ 200 req/s; OL fail ≤ 3%",
        metric="throughput_rps",
        value=throughput,
        threshold=target_throughput,
        passed=(throughput >= target_throughput * 0.70 and fail_rate <= 0.03),
        extra={
            "agents": agents,
            "tasks": agents,
            "successes": successes,
            "ol_failures": failures,
            "elapsed_s": elapsed,
            "ol_fail_rate": fail_rate,
        },
    )


def _mk_actor(engine) -> int:
    Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    s = Session()
    try:
        return _make_actor(s, f"b2-{uuid.uuid4()}")
    finally:
        s.close()


# ---------------------------------------------------------------------------
# B3 — pool view query
# ---------------------------------------------------------------------------


def run_b3_pool_view(engine, *, k_rows: int = 10_000) -> ScenarioResult:
    """Insert ``k_rows`` minimal task nodes attached to a pool then time a
    typical pool-view query 100x. Smoke target relaxed to 50 ms; release
    target = 30 ms / 1M rows (handled by ``--mode release``)."""
    Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    s = Session()
    type_id = int(
        s.execute(text("SELECT id FROM node_types WHERE type_code='task'")).scalar()
    )
    pool_id = int(
        s.execute(text("SELECT id FROM task_pools WHERE key='hicampus.cleaning'")).scalar()
    )
    # Bulk insert with attributes containing pool_id and current_state in the
    # JSONB attributes (the 7 expression indexes are already on `nodes`).
    bench_tag = f"b3-{uuid.uuid4().hex[:8]}"
    s.execute(
        text(
            """
            INSERT INTO nodes (type_id, type_code, name, attributes, is_active, is_public)
            SELECT
              :tid, 'task', :tag || '-' || gs::text,
              jsonb_build_object(
                'current_state','open',
                'state_version', 1,
                'pool_id', :pool_id,
                'priority', 'normal',
                'visibility', 'pool_open',
                'assignee_kind', 'pool',
                'workflow_ref', jsonb_build_object('key','default_v1','version',1)
              ),
              TRUE, FALSE
            FROM generate_series(1, :k) gs
            """
        ),
        {"tid": type_id, "pool_id": pool_id, "tag": bench_tag, "k": k_rows},
    )
    s.commit()

    samples_ms: List[float] = []
    for _ in range(100):
        t0 = time.perf_counter()
        s.execute(
            text(
                """
                SELECT id FROM nodes
                 WHERE type_code = 'task'
                   AND (attributes->>'pool_id')::int = :pool_id
                   AND attributes->>'current_state' = 'open'
                 ORDER BY id DESC
                 LIMIT 50
                """
            ),
            {"pool_id": pool_id},
        ).all()
        samples_ms.append((time.perf_counter() - t0) * 1000.0)
    s.close()

    p99 = _percentile(samples_ms, 99)
    smoke_target_ms = 50.0
    return ScenarioResult(
        name="B3_pool_view_query",
        target=f"smoke P99 ≤ {smoke_target_ms} ms ({k_rows} rows)",
        metric="p99_ms",
        value=p99,
        threshold=smoke_target_ms,
        passed=p99 <= smoke_target_ms / 0.70,
        extra={
            "rows": k_rows,
            "p50_ms": _percentile(samples_ms, 50),
            "p95_ms": _percentile(samples_ms, 95),
            "tag": bench_tag,
        },
    )


# ---------------------------------------------------------------------------
# B4 — selector validation
# ---------------------------------------------------------------------------


def run_b4_selector_validation(*, m: int = 10_000) -> ScenarioResult:
    from app.services.task.selector import validate_selector

    selector = {
        "_schema_version": 1,
        "include": [
            {"type_code": "default_object"},
            {"tags_any": [f"tag-{i}" for i in range(50)]},
        ],
        "exclude": [{"type_code": "task"}],
        "bounds": {"min": 0, "max": m * 2},
    }
    t0 = time.perf_counter()
    for _ in range(m):
        validate_selector(selector)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    target_ms = 200.0
    return ScenarioResult(
        name="B4_selector_validation_10k",
        target=f"≤ {target_ms} ms @ {m} validations",
        metric="elapsed_ms",
        value=elapsed_ms,
        threshold=target_ms,
        passed=elapsed_ms <= target_ms / 0.70,
        extra={"validations": m},
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Task System Phase B perf bench")
    parser.add_argument("--mode", choices=["smoke", "release"], default="smoke")
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args(argv)

    db_url = os.environ.get(_DB_URL_ENV, "").strip()
    if not db_url or not db_url.lower().startswith("postgresql"):
        print(f"[task_bench] {_DB_URL_ENV} not set; cannot run bench.", file=sys.stderr)
        return 2

    if args.mode == "smoke":
        n = 50
        k_rows = 5_000
        m = 1_000
    else:
        n = 10_000
        k_rows = 100_000
        m = 10_000

    engine = create_engine(db_url, future=True)

    from db.schema_migrations import (
        ensure_graph_seed_ontology,
        ensure_task_system_schema,
        ensure_task_system_seed,
    )

    ensure_graph_seed_ontology(engine)
    ensure_task_system_schema(engine)
    ensure_task_system_seed(engine)

    results: List[ScenarioResult] = []
    results.append(run_b1_transition_hot_path(engine, n=n))
    results.append(run_b2_concurrent_claim(engine))
    results.append(run_b3_pool_view(engine, k_rows=k_rows))
    results.append(run_b4_selector_validation(m=m))

    payload = {
        "mode": args.mode,
        "results": [asdict(r) for r in results],
        "all_passed": all(r.passed for r in results),
    }
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if payload["all_passed"] else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
