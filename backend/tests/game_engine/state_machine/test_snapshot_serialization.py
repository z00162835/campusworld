"""StateMachineSnapshot serialization round-trip tests."""
from __future__ import annotations

import pytest

from app.game_engine.agent_runtime.state_machine import StateMachineSnapshot


@pytest.mark.unit
def test_snapshot_to_from_dict_roundtrip():
    snap = StateMachineSnapshot(
        schema_version="1",
        current_state="check",
        turn_count=3,
        replan_count=1,
        completed_states=("plan", "do"),
        last_event="check_retry",
    )
    restored = StateMachineSnapshot.from_dict(snap.to_dict())
    assert restored == snap


@pytest.mark.unit
def test_snapshot_from_dict_defaults():
    restored = StateMachineSnapshot.from_dict({})
    assert restored.schema_version == "1"
    assert restored.current_state == ""
    assert restored.turn_count == 0
    assert restored.replan_count == 0
    assert restored.completed_states == ()
    assert restored.last_event is None
