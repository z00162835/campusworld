"""
POST /api/v1/auth/login 使用与 SSH 相同的图账号认证，JWT sub 为 account node id。
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.api.v1.endpoints import auth as auth_module
from app.core.security import ALGORITHM, _get_secret_key


@pytest.fixture
def auth_client():
    app = FastAPI()
    app.include_router(auth_module.router, prefix="/api/v1/auth")
    return TestClient(app, raise_server_exceptions=False)


def test_login_success_jwt_sub_is_account_id(auth_client):
    with patch.object(auth_module, "game_handler") as gh:
        gh.authenticate_user.return_value = {
            "success": True,
            "user_id": 42,
            "username": "alice",
        }
        r = auth_client.post(
            "/api/v1/auth/login",
            data={"username": "alice", "password": "secret"},
        )
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    payload = jwt.decode(
        body["access_token"],
        _get_secret_key(),
        algorithms=[ALGORITHM],
    )
    assert payload["sub"] == "42"
    assert payload.get("username") == "alice"
    gh.authenticate_user.assert_called_once()
    call_kw = gh.authenticate_user.call_args[1]
    assert call_kw["username"] == "alice"
    assert call_kw["password"] == "secret"


def test_login_failure_401(auth_client):
    with patch.object(auth_module, "game_handler") as gh:
        gh.authenticate_user.return_value = {
            "success": False,
            "error": "密码错误",
        }
        r = auth_client.post(
            "/api/v1/auth/login",
            data={"username": "alice", "password": "wrong"},
        )
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid username or password"
