"""Live-only CLI runner for AICO Agent Tool Eval."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from app.game_engine.agent_runtime.eval.adapters.aico import AicoEvalAdapter
from app.game_engine.agent_runtime.eval.adapters.base import AgentEvalAdapter
from app.game_engine.agent_runtime.eval.config import DEFAULT_CONFIG_PATH, EvalToolConfig, load_eval_config
from app.game_engine.agent_runtime.eval.graders import grade_prediction, verdict_from_scores
from app.game_engine.agent_runtime.eval.metrics import build_report, evaluate_report_gates, report_passes_initial_gates
from app.game_engine.agent_runtime.eval.schema import AgentToolEvalCase, EvalPair, load_cases_jsonl, write_jsonl

def adapter_by_name(name: str, *, config: EvalToolConfig) -> AgentEvalAdapter:
    key = (name or '').strip().lower()
    if key == 'aico':
        return AicoEvalAdapter(runtime_config=config.aico)
    raise ValueError(f'unknown eval adapter: {name}')


def run_eval(*, config: EvalToolConfig, adapter_name: str | None=None, cases_path: Path | None=None, adapter: AgentEvalAdapter | None=None) -> List[EvalPair]:
    adapter_name = adapter_name or config.adapter
    adapter = adapter or adapter_by_name(adapter_name, config=config)
    cases_path = cases_path or config.cases_path
    cases = load_cases_jsonl(cases_path)
    pairs: List[EvalPair] = []
    try:
        for case in cases:
            prediction = adapter.run_live_case(case)
            scores = grade_prediction(case, prediction)
            pairs.append(EvalPair(case=case, prediction=prediction, scores=scores, verdict=verdict_from_scores(scores)))
    finally:
        close = getattr(adapter, 'close', None)
        if callable(close):
            close()
    return pairs


def resolve_cases_path_for_suite(config: EvalToolConfig, suite: str | None) -> Path:
    chosen = str(suite or 'gate').strip().lower()
    if chosen in config.cases_by_suite:
        return config.cases_by_suite[chosen]
    if chosen == 'default':
        return config.cases_path
    raise ValueError(f'unknown eval suite: {chosen}; available={sorted(config.cases_by_suite.keys())}')


def validate_case_governance(cases: List[AgentToolEvalCase], *, expected_suite: str, config: EvalToolConfig) -> None:
    gov = config.dataset_governance
    errors: List[str] = []
    seen_ids = set()
    expected_suite_norm = str(expected_suite or '').strip().lower()
    for (idx, case) in enumerate(cases, start=1):
        if case.example_id in seen_ids:
            errors.append(f'line {idx}: duplicate example_id={case.example_id}')
        seen_ids.add(case.example_id)
        if gov.require_tags and not case.tags:
            errors.append(f'line {idx}: case {case.example_id} missing tags')
        intent = str((case.metadata or {}).get('intent') or '').strip()
        if gov.require_intent_metadata and not intent:
            errors.append(f'line {idx}: case {case.example_id} missing metadata.intent')
        dataset_tier = str((case.metadata or {}).get('dataset_tier') or '').strip().lower()
        if gov.require_dataset_tier and not dataset_tier:
            errors.append(f'line {idx}: case {case.example_id} missing metadata.dataset_tier')
        elif dataset_tier and expected_suite_norm and dataset_tier != expected_suite_norm:
            errors.append(
                f'line {idx}: case {case.example_id} dataset_tier={dataset_tier} != requested suite={expected_suite_norm}'
            )
    if errors and gov.strict:
        sample = '; '.join(errors[:8])
        raise ValueError(f'dataset governance validation failed ({len(errors)} issue(s)): {sample}')


def write_report(path: Path, report: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8')


def _gate_failure_payload(report: Dict[str, object], report_path: Path) -> Dict[str, object]:
    (_, failed_metrics) = evaluate_report_gates(report, mode='live')
    return {
        'gate_passed': False,
        'adapter': report.get('adapter'),
        'mode': report.get('mode'),
        'report': str(report_path),
        'failed_metrics': failed_metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Run live AICO Agent Tool Eval')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument('--adapter', default=None)
    parser.add_argument('--suite', default='gate', help='Case suite name in config.cases_by_suite (default: gate)')
    parser.add_argument('--cases', type=Path, default=None)
    parser.add_argument('--out', type=Path, default=None, help='Output pairs JSONL')
    parser.add_argument('--report', type=Path, default=None, help='Output aggregate report JSON')
    parser.add_argument(
        '--no-enforce-gates',
        action='store_true',
        help='Do not fail the process when initial live gates fail (debug only).',
    )
    parser.add_argument(
        '--skip-dataset-governance',
        action='store_true',
        help='Skip dataset governance checks (debug only).',
    )
    args = parser.parse_args()
    cfg = load_eval_config(args.config)
    adapter_name = args.adapter or cfg.adapter
    chosen_cases_path = args.cases or resolve_cases_path_for_suite(cfg, args.suite)
    out_path = args.out or cfg.pairs_path
    report_path = args.report or cfg.report_path
    if not args.skip_dataset_governance:
        cases = load_cases_jsonl(chosen_cases_path)
        validate_case_governance(cases, expected_suite=args.suite, config=cfg)
    pairs = run_eval(config=cfg, adapter_name=adapter_name, cases_path=chosen_cases_path)
    write_jsonl(out_path, [p.to_dict() for p in pairs])
    report = build_report(
        pairs,
        adapter=adapter_name,
        mode='live',
        live_gate_thresholds=cfg.gate_policy.live,
    )
    write_report(report_path, report)
    enforce_gates = cfg.gate_policy.enforce and (not args.no_enforce_gates)
    if enforce_gates and not report_passes_initial_gates(report, tolerance=cfg.gate_policy.tolerance):
        print(json.dumps(_gate_failure_payload(report, report_path), ensure_ascii=False))
        return 2
    print(
        json.dumps(
            {
                'pairs': len(pairs),
                'report': str(report_path),
                'out': str(out_path),
                'config': str(cfg.config_path),
                'suite': str(args.suite or 'gate'),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
