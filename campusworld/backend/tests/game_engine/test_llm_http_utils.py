"""Tests for LLM HTTP helper error logging."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.game_engine.agent_runtime.llm_providers import http_utils


@pytest.mark.unit
def test_summarize_llm_request_body_hides_large_system():
    body = {
        "model": "m1",
        "max_tokens": 100,
        "system": "x" * 50_000,
        "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        "tools": [{"name": "find", "description": "d", "input_schema": {"type": "object"}}],
    }
    s = http_utils._summarize_llm_request_body(body)
    assert "m1" in s
    assert "chars=50000" in s or "50000" in s
    assert "find" in s
    assert "x" * 100 not in s


@pytest.mark.unit
def test_httpx_post_json_logs_error_before_raise(caplog):
    import logging

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = '{"error":{"type":"invalid_request","message":"bad tool"}}'
    mock_resp.raise_for_status.side_effect = __import__(
        "httpx", fromlist=["HTTPStatusError"]
    ).HTTPStatusError("bad", request=MagicMock(), response=mock_resp)

    with caplog.at_level(logging.ERROR, logger="app.game_engine.llm_http"):
        with patch("httpx.Client") as client_cls:
            inst = MagicMock()
            client_cls.return_value.__enter__.return_value = inst
            inst.post.return_value = mock_resp
            with pytest.raises(Exception):
                http_utils.httpx_post_json(
                    "https://example.com/v1/messages",
                    headers={"Authorization": "Bearer x"},
                    body={"model": "m", "messages": []},
                    timeout=1.0,
                )

    joined = caplog.text
    assert "llm_http_error" in joined
    assert "400" in joined
    assert "bad tool" in joined
