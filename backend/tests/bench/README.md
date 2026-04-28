# Task System Performance Bench (Phase B)

Reference: [`docs/task/SPEC/SPEC.md` §1.8.2](../../../docs/task/SPEC/SPEC.md#182-性能基线oq-30).

## What we measure (Phase B subset)

| ID | Scenario | Target |
|----|----------|--------|
| B1 | `transition` single-task hot path | P99 ≤ 50 ms |
| B2 | 32-agent concurrent `claim` on same task | ≥ 200 req/s; optimistic-lock failure ≤ 3% |
| B3 | Pool view query against 10k tasks (smoke; spec target = 1M) | P99 ≤ 30 ms (smoke ≤ 50 ms) |
| B4 | `scope_selector` validation @ 10k targets (validate-only; SQL plan deferred to Phase C) | ≤ 200 ms |

## Modes

- **smoke** (default in CI): N=200 transitions, K=10k pool rows, M=10k selector targets. Fast, deterministic.
- **release**: N=10000, K=100k, M=10k. Manually triggered from release pipeline.

```bash
# Smoke (CI):
CAMPUSWORLD_TEST_DATABASE_URL=postgresql+psycopg2://... \
  python -m tests.bench.task_bench --mode smoke --out tests/bench/baselines/$(date +%F).json

# Release:
CAMPUSWORLD_TEST_DATABASE_URL=postgresql+psycopg2://... \
  python -m tests.bench.task_bench --mode release --out tests/bench/baselines/$(date +%F)-release.json
```

The exit code is `0` when **all four** scenarios meet at least 70% of the target
(first-version drift allowance). CI fails the PR if any baseline is missed.
