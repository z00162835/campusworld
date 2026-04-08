from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from campus.connection import WSConnection


def _discard_receive_loop_task(coro):
    """Avoid starting _receive_loop in unit tests; close coroutine to silence warnings."""
    try:
        coro.close()
    except (RuntimeError, TypeError):
        pass
    t = MagicMock()
    t.cancel = MagicMock()
    return t


@pytest.mark.asyncio
async def test_connect_success():
    mock_ws = AsyncMock()
    mock_ws.send = AsyncMock()
    mock_ws.recv = AsyncMock(
        return_value='{"type":"connected","user":{"user_id":"1","username":"a","session_id":"s"}}'
    )

    with patch("campus.connection.websockets.connect", new_callable=AsyncMock, return_value=mock_ws):
        with patch("asyncio.create_task", side_effect=_discard_receive_loop_task):
            conn = WSConnection("localhost", 8000, False)
            ok = await conn.connect("tok")
    assert ok is True
    assert conn.user_info is not None
    assert conn.user_info.username == "a"


@pytest.mark.asyncio
async def test_connect_rejects_when_not_connected():
    mock_ws = AsyncMock()
    mock_ws.send = AsyncMock()
    mock_ws.recv = AsyncMock(return_value='{"type":"error","message":"x"}')

    with patch("campus.connection.websockets.connect", new_callable=AsyncMock, return_value=mock_ws):
        with patch("asyncio.create_task", side_effect=_discard_receive_loop_task):
            conn = WSConnection("localhost", 8000, False)
            ok = await conn.connect("tok")
    assert ok is False
