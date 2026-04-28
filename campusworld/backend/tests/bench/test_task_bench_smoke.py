"""Phase B PR6: smoke-import test for ``task_bench`` + B4 selector run.

This test does NOT need a database; it imports the bench module and runs the
pure-Python ``B4_selector_validation`` scenario at low M to verify the wiring.
The full bench (B1/B2/B3) is exercised by the postgres_integration suite or
by the release pipeline — see ``tests/bench/README.md``.
"""

from __future__ import annotations


def test_task_bench_module_imports():
    from tests.bench import task_bench

    assert hasattr(task_bench, "run_b1_transition_hot_path")
    assert hasattr(task_bench, "run_b2_concurrent_claim")
    assert hasattr(task_bench, "run_b3_pool_view")
    assert hasattr(task_bench, "run_b4_selector_validation")
    assert hasattr(task_bench, "main")


def test_b4_selector_validation_runs_under_target():
    from tests.bench.task_bench import run_b4_selector_validation

    result = run_b4_selector_validation(m=200)
    assert result.metric == "elapsed_ms"
    assert result.value < 1000.0  # generous CI bound; target is 200 ms @ 10k.
    assert result.extra["validations"] == 200


def test_percentile_helper_matches_basic_expectations():
    from tests.bench.task_bench import _percentile

    assert _percentile([], 99) == 0.0
    assert _percentile([10.0], 99) == 10.0
    samples = [float(i) for i in range(1, 101)]
    # k = round(pct/100 * (n-1)) — 50% of 99 → 49.5 → round-to-even → 50 → samples[50] = 51.0
    assert _percentile(samples, 50) == 51.0
    # 99% of 99 → 98.01 → 98 → samples[98] = 99.0
    assert _percentile(samples, 99) == 99.0
    assert _percentile(samples, 0) == 1.0
    assert _percentile(samples, 100) == 100.0
