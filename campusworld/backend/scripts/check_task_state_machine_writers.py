#!/usr/bin/env python3
"""CI guard: enforce single-write-path for task system writes (SPEC §1.3 I3).

Scans the backend source tree and rejects any UPDATE / INSERT into
``task_state_transitions``, ``task_outbox`` or ``task_assignments`` from files
outside an explicit allow-list. The state machine module is the SSOT for
state transitions; seed / migration helpers and replay tooling are also
allowed because they form the bootstrap surface.

Run as ``python -m backend.scripts.check_task_state_machine_writers`` or via
the ``tests/test_static_task_writes.py`` test wrapper.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable, List, Tuple


_BACKEND_ROOT = Path(__file__).resolve().parents[1]


# Files allowed to write to the protected tables.
ALLOWED_PATHS: tuple[str, ...] = (
    "app/services/task/task_state_machine.py",
    "app/services/task/task_replay.py",
    "db/seeds/task_seed.py",
    "db/schema_migrations.py",
    "db/schemas/database_schema.sql",
    # the script itself + tests reference the literals; whitelist them.
    "scripts/check_task_state_machine_writers.py",
)


# Tables guarded by this lint.
GUARDED_TABLES: tuple[str, ...] = (
    "task_state_transitions",
    "task_outbox",
    "task_assignments",
)


# Regex for "INSERT INTO <table>" / "UPDATE <table>" in any case.
WRITE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(rf"\b(INSERT\s+INTO|UPDATE)\s+{re.escape(name)}\b", re.IGNORECASE)
    for name in GUARDED_TABLES
)


# Regex for "UPDATE nodes ... attributes ..." touching current_state / state_version.
NODES_STATE_WRITE = re.compile(
    r"UPDATE\s+nodes\b.*?(current_state|state_version)",
    re.IGNORECASE | re.DOTALL,
)


def _iter_source_files(root: Path) -> Iterable[Path]:
    for ext in ("*.py", "*.sql"):
        for path in root.rglob(ext):
            # Skip caches, virtualenvs, build artefacts.
            parts = path.parts
            if any(p.startswith(".") for p in parts):
                continue
            if "__pycache__" in parts or "node_modules" in parts:
                continue
            if "tests" in parts:
                # Tests legitimately exercise raw INSERTs to the guarded tables.
                continue
            yield path


def _is_allowed(path: Path) -> bool:
    rel = path.relative_to(_BACKEND_ROOT).as_posix()
    return rel in ALLOWED_PATHS


def find_violations() -> List[Tuple[Path, int, str]]:
    violations: List[Tuple[Path, int, str]] = []
    for path in _iter_source_files(_BACKEND_ROOT):
        if _is_allowed(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for pat in WRITE_PATTERNS:
            for m in pat.finditer(text):
                line_no = text.count("\n", 0, m.start()) + 1
                violations.append((path, line_no, m.group(0)))
        for m in NODES_STATE_WRITE.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            violations.append((path, line_no, "UPDATE nodes ... current_state/state_version"))
    return violations


def main() -> int:
    violations = find_violations()
    if not violations:
        print("[ok] no direct writes to task_state_transitions / task_outbox / task_assignments")
        return 0
    print("[fail] task system single-write-path invariant breached (SPEC §1.3 I3):")
    for path, line, snippet in violations:
        rel = path.relative_to(_BACKEND_ROOT).as_posix()
        print(f"  {rel}:{line}: {snippet}")
    print("\nAllowed writers:")
    for p in ALLOWED_PATHS:
        print(f"  - {p}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
