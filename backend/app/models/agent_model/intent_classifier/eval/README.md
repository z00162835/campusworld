# Intent Classifier Evaluation Notes

## Core KPI (shared definitions)
- `informational_mutate_plan_rate`
  - Ratio of informational requests that still plan mutate tools.
- `clarify_instead_of_guess_rate`
  - Ratio of ambiguous requests where system asks clarification rather than guessing execution.

## Window
- Use day-based window (latest N days) per current decision.

## Per-agent thresholds
- Metric definitions are shared.
- Threshold values are agent-specific (`config/defaults.yaml` + runtime overrides).

