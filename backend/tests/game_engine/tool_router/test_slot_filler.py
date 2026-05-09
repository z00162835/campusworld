from __future__ import annotations

import pytest

from app.game_engine.agent_runtime.model_backends.protocols import ChatGenerativeResult
from app.game_engine.agent_runtime.model_backends.stubs import StubChatGenerativeBackend
from app.game_engine.agent_runtime.tool_router.slot_filler import SlotFiller, validate_slot_against_schema

_VALID = (
    '{"target_hint":null,"named_spans":[],"entities":[],"mandatory_tools":["look"]}'
)


@pytest.mark.unit
def test_validate_slot_against_schema_rejects_incomplete() -> None:
    assert not validate_slot_against_schema({})
    assert not validate_slot_against_schema(
        {"target_hint": None, "named_spans": [], "entities": []}  # missing mandatory_tools
    )


@pytest.mark.unit
def test_validate_slot_accepts_schema_instance() -> None:
    assert validate_slot_against_schema(
        {
            "target_hint": None,
            "named_spans": [],
            "entities": [],
            "mandatory_tools": [],
        }
    )


@pytest.mark.unit
def test_slot_filler_stub_returns_mandatory() -> None:
    filler = SlotFiller(StubChatGenerativeBackend(fixed_text=_VALID))
    obj, mandatory = filler.extract(
        user_message="look around",
        enrich_query="World snapshot:\nhere",
        repair=False,
    )
    assert obj is not None
    assert mandatory == ["look"]


class _SeqChatBackend:
    backend_kind = "seq_stub"
    model_id = "seq"

    def __init__(self, texts: list[str]) -> None:
        self._texts = texts
        self._i = 0

    def complete_chat(self, messages, *, max_new_tokens: int = 256, temperature: float = 0.0):
        text = self._texts[self._i]
        self._i += 1
        return ChatGenerativeResult(
            text=text,
            latency_ms=0.0,
            backend_kind=self.backend_kind,
            model_id=self.model_id,
        )


@pytest.mark.unit
def test_slot_filler_repair_after_invalid_json() -> None:
    filler = SlotFiller(
        _SeqChatBackend(
            [
                "not json",
                '{"target_hint":null,"named_spans":[],"entities":[],"mandatory_tools":["describe"]}',
            ]
        )
    )
    obj, mandatory = filler.extract(
        user_message="examine #1",
        enrich_query="Rule hints:\n- x",
        repair=True,
    )
    assert obj is not None
    assert mandatory == ["describe"]
