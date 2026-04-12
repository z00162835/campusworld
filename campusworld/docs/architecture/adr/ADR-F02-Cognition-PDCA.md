# ADR-F02: Cognition — PDCA as Default Framework

## Status

Accepted — 2026-04-09

## Context

Multiple thinking frameworks (PDCA, OODA, …) require **different control-flow graphs**. Tooling and memory must not be embedded inside a single monolithic runner.

## Decision

1. **`ThinkingFramework` protocol** — Each framework implements its own **main loop** (phase transitions, re-entry, termination). The reference implementation is **`PDCAFramework`** (`plan` → `do` → `check` → `act`).

2. **Injected ports** — `MemoryPort` (read/write raw + LTM hooks) and `ToolExecutor` (command/tool dispatch) are **passed in**; frameworks do not import DAOs directly.

3. **Default registry mapping** — If an agent type does not override cognition, the worker registry defaults to **`PDCAFramework`**.

## Consequences

- Additional frameworks are **new modules** with their own `run()` graphs, not `if framework ==` branches in one class.
