# Training and Annotation Handbook

## 1) Labeling schema
- `informational`: asks examples/syntax/usage/help, no state change intent.
- `verify_state`: asks current/existence/status checks, read-only.
- `execute`: explicit action request with confirmation signal.

## 2) Conflict handling
- If sentence mixes example + action but no confirmation, label as `informational`.
- If explicit confirmation exists (e.g. `请执行`, `确认执行`, `yes, execute`), label as `execute`.
- If uncertainty remains, choose `informational` and add note.

## 3) Human workflow
1. Annotator labels raw samples.
2. Reviewer performs arbitration on conflict cases.
3. Curator publishes merged dataset with new data version.
4. Trainer runs reproducible training/export.
5. Validator checks KPI targets before rollout.

## 4) Data quality checks
- Inter-annotator agreement on conflict subset.
- Class distribution sanity (avoid single-label collapse).
- Language coverage for zh-CN/en-US.

## 5) KPI validation
- Shared metric definitions:
  - informational_mutate_plan_rate
  - clarify_instead_of_guess_rate
- Thresholds are per-agent and configured separately.

## 6) Trainer runtime environment

Training/export scripts assume the repo-standard **Conda `campusworld`** Python (`conda activate campusworld`, working directory `backend`), plus PyTorch (platform-specific) and `requirements/ml-intent-classifier.txt`. Commands and outputs: [`train/README.md`](train/README.md).

At ~10k curated samples, prefer the defaults in `config/defaults.yaml` (`training:`) as a starting point (Qwen3 4B instruct, ~10% val, modest epochs, LoRA rank 32); adjust batch/accumulation for GPU memory before chasing higher epochs or rank.

