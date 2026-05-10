# Docs Agent Guide

Follow root `AGENTS.md` first. This file covers documentation governance.

## Source Of Truth

- Module contracts live in `docs/<module>/SPEC/SPEC.md`.
- Feature contracts live only in `docs/<module>/SPEC/features/`.
- Acceptance criteria live in `docs/<module>/SPEC/ACCEPTANCE.md`.
- Backlog and deferred work live in `docs/<module>/SPEC/TODO.md`.

## Governance Rules

- Do not create parallel feature specs outside `features/`.
- Do not duplicate full feature text in module `SPEC.md`; link and summarize instead.
- When behavior changes, update the nearest module SPEC and acceptance notes.
- When implementation contradicts docs, either update docs in the same change or call out the drift.
- Avoid `Fxx` labels in implementation code; docs may use feature names where they are the contract source.

## Style

- Keep docs factual and executable.
- Prefer short invariants, verification steps, and links over long repeated architecture prose.
- Mark planned but unimplemented architecture as RFC or future work.
- Keep examples aligned with actual paths and commands in the repository.
