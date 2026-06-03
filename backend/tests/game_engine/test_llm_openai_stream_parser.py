from __future__ import annotations

from app.game_engine.agent_runtime.llm_providers.http_utils import parse_openai_compatible_sse_lines


def test_parse_openai_compatible_sse_lines_orders_deltas():
    deltas: list[str] = []
    lines = [
        'data: {"choices":[{"delta":{"content":"Hel"}}]}',
        'data: {"choices":[{"delta":{"content":"lo"}}]}',
        'data: [DONE]',
    ]
    full = parse_openai_compatible_sse_lines(lines, on_delta=deltas.append)
    assert full == 'Hello'
    assert deltas == ['Hel', 'lo']
