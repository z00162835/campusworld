"""Aggregate metrics for Agent Tool Eval reports."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Sequence, Tuple

from app.game_engine.agent_runtime.eval.config import EvalGateMetricConfig
from app.game_engine.agent_runtime.eval.schema import EvalPair


def _default_live_gate_thresholds() -> Dict[str, Dict[str, float | str]]:
    return {
        'live_trace_presence': {'op': 'gte', 'value': 1.0},
        'final_reply_after_tool': {'op': 'gte', 'value': 1.0},
        'illegal_tool_rate': {'op': 'lte', 'value': 0.0},
        'schema_violation_rate': {'op': 'lte', 'value': 0.0},
    }


def build_report(
    pairs: Sequence[EvalPair],
    *,
    adapter: str,
    mode: str,
    live_gate_thresholds: Dict[str, EvalGateMetricConfig] | None = None,
) -> Dict[str, Any]:
    n = len(pairs)
    verdicts = Counter(p.verdict for p in pairs)
    score_buckets: Dict[str, List[float]] = defaultdict(list)
    failure_reasons: Counter[str] = Counter()
    by_tool: Dict[str, Dict[str, int]] = defaultdict(lambda: {'n': 0, 'failures': 0})
    for p in pairs:
        tools = set(p.case.expected_tools) | set(p.case.mandatory_tools) | set(p.prediction.predicted_tools)
        for t in tools or {'(none)'}:
            by_tool[t]['n'] += 1
            if p.verdict != 'pass':
                by_tool[t]['failures'] += 1
        for s in p.scores:
            if s.value is not None:
                score_buckets[s.name].append(float(s.value))
            if not s.passed:
                failure_reasons[s.name] += 1
    score_summary = {
        name: (sum(values) / len(values) if values else None)
        for (name, values) in sorted(score_buckets.items())
    }
    live_gates_cfg = live_gate_thresholds or {
        name: EvalGateMetricConfig(op=str(spec.get('op') or 'eq'), value=float(spec.get('value') or 0.0))
        for (name, spec) in _default_live_gate_thresholds().items()
    }
    live_gates_for_report = {
        metric_name: {'op': metric_cfg.op, 'value': metric_cfg.value}
        for (metric_name, metric_cfg) in sorted(live_gates_cfg.items())
    }
    return {
        'adapter': adapter,
        'mode': mode,
        'n_pairs': n,
        'pass_rate': verdicts.get('pass', 0) / n if n else 0.0,
        'verdicts': dict(sorted(verdicts.items())),
        'scores': score_summary,
        'failure_reasons': dict(sorted(failure_reasons.items())),
        'by_tool': dict(sorted(by_tool.items())),
        'gate_thresholds': {
            'live': live_gates_for_report,
        },
    }


def evaluate_report_gates(
    report: Dict[str, Any],
    *,
    mode: str='live',
    tolerance: float=1e-9,
) -> Tuple[bool, List[Dict[str, float | str]]]:
    scores = report.get('scores') if isinstance(report.get('scores'), dict) else {}
    thresholds = report.get('gate_thresholds') if isinstance(report.get('gate_thresholds'), dict) else {}
    mode_thresholds = thresholds.get(mode) if isinstance(thresholds.get(mode), dict) else {}
    failures: List[Dict[str, float | str]] = []
    for (metric_name, spec) in mode_thresholds.items():
        if not isinstance(spec, dict):
            continue
        op = str(spec.get('op') or 'eq').strip().lower()
        expected = float(spec.get('value') or 0.0)
        actual = float(scores.get(metric_name) or 0.0)
        passed = False
        if op == 'gte':
            passed = actual + tolerance >= expected
        elif op == 'lte':
            passed = actual - tolerance <= expected
        else:
            passed = abs(actual - expected) <= tolerance
        if not passed:
            failures.append({'name': str(metric_name), 'op': op, 'actual': actual, 'expected': expected})
    return (not failures, failures)


def report_passes_initial_gates(report: Dict[str, Any], *, tolerance: float=1e-9) -> bool:
    mode = str(report.get('mode') or '')
    if mode == 'live':
        (passed, _) = evaluate_report_gates(report, mode='live', tolerance=tolerance)
        return passed
    return True
