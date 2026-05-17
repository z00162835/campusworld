"""Promote corrected eval pairs into regression cases."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Iterable, List

from app.game_engine.agent_runtime.eval.config import DEFAULT_CONFIG_PATH, load_eval_config
from app.game_engine.agent_runtime.eval.schema import AgentToolEvalCase, EvalPair, load_pairs_jsonl, write_jsonl


def promoted_cases_from_pairs(pairs: Iterable[EvalPair]) -> List[AgentToolEvalCase]:
    out: List[AgentToolEvalCase] = []
    for pair in pairs:
        corr = pair.correction
        if corr.status == 'discarded':
            continue
        case = pair.case
        if corr.corrected_expected_tools is not None:
            case.expected_tools = list(corr.corrected_expected_tools)
        if corr.corrected_mandatory_tools is not None:
            case.mandatory_tools = list(corr.corrected_mandatory_tools)
        if corr.corrected_forbidden_tools is not None:
            case.forbidden_tools = list(corr.corrected_forbidden_tools)
        if corr.corrected_expected_args is not None:
            case.expected_args = dict(corr.corrected_expected_args)
        meta: Dict[str, object] = dict(case.metadata or {})
        meta['promoted_from_pair'] = True
        meta['review_status'] = corr.status
        if corr.reviewer_note:
            meta['reviewer_note'] = corr.reviewer_note
        case.metadata = meta
        out.append(case)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description='Promote corrected Agent Tool Eval pairs to regression cases')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument('--pairs', type=Path, default=None)
    parser.add_argument('--out', type=Path, default=None)
    args = parser.parse_args()
    cfg = load_eval_config(args.config)
    pairs_path = args.pairs or cfg.corrected_pairs_path
    out_path = args.out or cfg.regression_cases_path
    pairs = load_pairs_jsonl(pairs_path)
    cases = promoted_cases_from_pairs(pairs)
    write_jsonl(out_path, [c.to_dict() for c in cases])
    print(f'wrote {len(cases)} regression cases to {out_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
