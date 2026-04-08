import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from campus.config import Config
from campus.__main__ import CampusClient
import json
from pathlib import Path


@pytest.fixture
def minimal_config(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"server": {"host": "127.0.0.1", "port": 8000}}), encoding="utf-8")
    return Config(str(p))


@pytest.mark.asyncio
async def test_login_success(minimal_config):
    client = CampusClient(minimal_config)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "jwt-abc"}

    mock_client_instance = AsyncMock()
    mock_client_instance.post = AsyncMock(return_value=mock_response)
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=None)

    with patch("campus.__main__.httpx.AsyncClient", return_value=mock_client_instance):
        ok, out = await client.login("alice", "pw")

    assert ok is True
    assert out == "jwt-abc"


@pytest.mark.asyncio
async def test_login_401(minimal_config):
    client = CampusClient(minimal_config)
    mock_response = MagicMock()
    mock_response.status_code = 401

    mock_client_instance = AsyncMock()
    mock_client_instance.post = AsyncMock(return_value=mock_response)
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=None)

    with patch("campus.__main__.httpx.AsyncClient", return_value=mock_client_instance):
        ok, out = await client.login("alice", "pw")

    assert ok is False
    assert "Invalid" in out


@pytest.mark.asyncio
async def test_run_rejects_empty_password(minimal_config, capsys):
    client = CampusClient(minimal_config)
    with patch("campus.__main__._try_load_saved_token", return_value=None):
        with patch("builtins.input", return_value="alice"):
            with patch("campus.__main__._prompt_password", return_value=""):
                await client.run()
    out = capsys.readouterr().out
    assert "Password is required" in out


@pytest.mark.asyncio
async def test_login_connection_error(minimal_config):
    import httpx

    client = CampusClient(minimal_config)
    mock_client_instance = AsyncMock()
    mock_client_instance.post = AsyncMock(side_effect=httpx.RequestError("fail", request=MagicMock()))
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=None)

    with patch("campus.__main__.httpx.AsyncClient", return_value=mock_client_instance):
        ok, out = await client.login("alice", "pw")

    assert ok is False
    assert "Connection error" in out
