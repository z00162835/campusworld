from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from app.game_engine.agent_runtime.llm_providers.http_utils import LlmRequestCancelled, httpx_post_json


@pytest.mark.unit
def test_httpx_post_json_cancel_during_blocking_post():
    cancel = threading.Event()
    gate = threading.Event()

    class _FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {'ok': True}

    def slow_post(*_args, **_kwargs):
        gate.set()
        time.sleep(2.0)
        return _FakeResponse()

    with patch('httpx.Client') as client_cls:
        client = MagicMock()
        client.post.side_effect = slow_post
        client_cls.return_value = client

        def run() -> None:
            time.sleep(0.05)
            cancel.set()

        threading.Thread(target=run, daemon=True).start()
        with pytest.raises(LlmRequestCancelled):
            httpx_post_json(
                'https://example.test/v1/messages',
                headers={},
                body={'model': 'm'},
                timeout=30.0,
                cancel_check=cancel.is_set,
            )
        assert gate.wait(timeout=1.0)
