"""Human review helpers for Agent Tool Eval pairs."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Optional

from app.game_engine.agent_runtime.eval.config import DEFAULT_CONFIG_PATH, load_eval_config
from app.game_engine.agent_runtime.eval.schema import EvalPair, PairCorrection, load_pairs_jsonl, write_jsonl

VALID_STATUSES = {'unreviewed', 'accepted', 'edited', 'discarded'}


def apply_pair_correction(pair: EvalPair, *, status: str, note: str='', discard_reason: str='') -> EvalPair:
    if status not in VALID_STATUSES:
        raise ValueError(f'invalid review status: {status}')
    pair.correction.status = status
    if note:
        pair.correction.reviewer_note = note
    if discard_reason:
        pair.correction.discard_reason = discard_reason
    return pair


def update_pair_statuses(pairs: Iterable[EvalPair], *, example_id: Optional[str], status: str, note: str='', discard_reason: str='') -> List[EvalPair]:
    out: List[EvalPair] = []
    matched = False
    for pair in pairs:
        if example_id is None or pair.case.example_id == example_id:
            apply_pair_correction(pair, status=status, note=note, discard_reason=discard_reason)
            matched = True
        out.append(pair)
    if example_id is not None and not matched:
        raise ValueError(f'example_id not found: {example_id}')
    return out


def interactive_review(pairs: List[EvalPair]) -> List[EvalPair]:
    for pair in pairs:
        if pair.correction.status != 'unreviewed':
            continue
        print(f'\n[{pair.case.example_id}] verdict={pair.verdict}')
        print(f'user: {pair.case.user_message}')
        print(f'expected: {pair.case.expected_tools} mandatory: {pair.case.mandatory_tools}')
        print(f'predicted: {pair.prediction.predicted_tools}')
        failures = [s for s in pair.scores if not s.passed]
        if failures:
            print('failures: ' + ', '.join(f.name for f in failures))
        choice = input('review action [a=accept, e=edited, d=discard, s=skip]: ').strip().lower()
        if choice == 'a':
            pair.correction = PairCorrection(status='accepted')
        elif choice == 'e':
            note = input('review note: ').strip()
            pair.correction.status = 'edited'
            pair.correction.reviewer_note = note
        elif choice == 'd':
            reason = input('discard reason: ').strip()
            pair.correction.status = 'discarded'
            pair.correction.discard_reason = reason
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description='Review Agent Tool Eval pairs')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument('--pairs', type=Path, default=None)
    parser.add_argument('--out', type=Path, default=None)
    parser.add_argument('--example-id', default=None, help='Non-interactive: update one example id')
    parser.add_argument('--status', choices=sorted(VALID_STATUSES), default=None, help='Non-interactive review status')
    parser.add_argument('--note', default='')
    parser.add_argument('--discard-reason', default='')
    args = parser.parse_args()
    cfg = load_eval_config(args.config)
    pairs_path = args.pairs or cfg.pairs_path
    out_path = args.out or cfg.corrected_pairs_path
    pairs = load_pairs_jsonl(pairs_path)
    if args.status:
        pairs = update_pair_statuses(pairs, example_id=args.example_id, status=args.status, note=args.note, discard_reason=args.discard_reason)
    else:
        pairs = interactive_review(pairs)
    write_jsonl(out_path, [p.to_dict() for p in pairs])
    print(f'wrote {len(pairs)} reviewed pairs to {out_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
