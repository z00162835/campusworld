from __future__ import annotations

import pytest

from app.models.agent_model.intent_classifier.runtime.inference import (
    clamp_intent_max_new_tokens,
    extract_json_object_for_intent,
)


@pytest.mark.unit
def test_clamp_intent_max_new_tokens_bounds():
    assert clamp_intent_max_new_tokens(96) == 96
    assert clamp_intent_max_new_tokens(4) == 8
    assert clamp_intent_max_new_tokens(9999) == 256
    assert clamp_intent_max_new_tokens("garbage") == 96


@pytest.mark.unit
def test_extract_json_object_for_intent_markdown_fence():
    raw = """```json
{"intent": "informational", "confidence": 0.5, "reason_tokens": []}
```
"""
    s = extract_json_object_for_intent(raw)
    assert '"intent"' in s


@pytest.mark.unit
def test_extract_json_object_for_intent_trailing_junk():
    raw = 'Sure. {"intent": "execute", "confidence": 1, "reason_tokens": ["x"]} thanks.'
    s = extract_json_object_for_intent(raw)
    assert s.startswith("{") and "execute" in s


@pytest.mark.unit
def test_extract_json_object_for_intent_empty_raises():
    with pytest.raises(ValueError):
        extract_json_object_for_intent("")
