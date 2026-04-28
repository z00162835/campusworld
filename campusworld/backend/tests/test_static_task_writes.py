"""Phase B PR3: CI guard — enforce task-system single-write-path invariant (SPEC I3).

Wraps ``scripts/check_task_state_machine_writers.py`` so it runs in the
standard pytest pipeline.
"""

from __future__ import annotations

import pytest

from scripts.check_task_state_machine_writers import find_violations


@pytest.mark.unit
def test_no_direct_task_writes_outside_state_machine():
    violations = find_violations()
    assert not violations, "Direct writes to task_* tables outside allow-list:\n" + "\n".join(
        f"  {p}:{ln}: {snip}" for p, ln, snip in violations
    )
