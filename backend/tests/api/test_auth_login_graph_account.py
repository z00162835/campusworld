"""
POST /api/v1/auth/login 使用与 SSH 相同的图账号认证，JWT sub 为 account node id。
"""

import logging
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
from app.core.security import ALGORITHM, _get_secret_key, create_access_token


@pytest.fixture
def db_session():
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    return session


@pytest.fixture
def auth_client(db_session):
    app = FastAPI()
    app.include_router(auth_module.router, prefix="/api/v1/auth")
    app.dependency_overrides[auth_module.get_db] = lambda: db_session
    return TestClient(app, raise_server_exceptions=False)


def test_login_success_jwt_sub_is_account_id(auth_client):
    access_token = create_access_token(subject="42", username="alice")
    with (
        patch.object(auth_module, "game_handler") as gh,
        patch.object(auth_module.AuthService, "cleanup_expired_tokens"),
        patch.object(auth_module.AuthService, "issue_tokens") as issue_tokens,
    ):
        gh.authenticate_user.return_value = {
            "success": True,
            "user_id": 42,
            "username": "alice",
        }
        issue_tokens.return_value = {
            "access_token": access_token,
            "refresh_token": "refresh-token",
            "csrf_token": "csrf-token",
            "expires_in": 900,
            "refresh_max_age": 3600,
            "idle_expires_in": 1800,
        }
        r = auth_client.post(
            "/api/v1/auth/login",
            data={"username": "alice", "password": "secret"},
        )
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert "refresh_token" not in body
    assert r.headers["Cache-Control"] == "no-store"
    set_cookie = r.headers.get("set-cookie", "")
    assert "access_token=" not in set_cookie
    assert "refresh_token=" in set_cookie
    assert "csrf_token=" in set_cookie
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


def test_refresh_unauthorized_response_clears_auth_cookies():
    response = auth_module._refresh_unauthorized_response("Invalid refresh token")

    set_cookie_headers = [
        value.decode("latin-1")
        for key, value in response.raw_headers
        if key.lower() == b"set-cookie"
    ]

    assert response.status_code == 401
    assert any(
        header.startswith("access_token=") and "Max-Age=0" in header
        for header in set_cookie_headers
    )
    assert any(
        (header.startswith("refresh_token=") or header.startswith("__Host-refresh_token=")) and "Max-Age=0" in header
        for header in set_cookie_headers
    )
    assert any(
        header.startswith("csrf_token=") and "Max-Age=0" in header
        for header in set_cookie_headers
    )
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Clear-Site-Data"] == '"cache", "storage"'


def test_login_rejects_disallowed_origin(auth_client):
    with patch.object(auth_module, "get_setting") as get_setting:
        get_setting.return_value = ["http://localhost:5173"]
        r = auth_client.post(
            "/api/v1/auth/login",
            data={"username": "alice", "password": "secret"},
            headers={"Origin": "https://evil.example"},
        )

    assert r.status_code == 403
    assert r.json()["detail"] == "Invalid request origin"


def test_refresh_requires_ajax_header(auth_client):
    r = auth_client.post("/api/v1/auth/refresh")

    assert r.status_code == 403
    assert r.json()["detail"] == "Missing required auth request header"


def test_refresh_ignores_explicit_body_token_without_cookie(auth_client, caplog):
    caplog.set_level(logging.DEBUG, logger=auth_module.__name__)
    r = auth_client.post(
        "/api/v1/auth/refresh",
        data={"refresh_token": "explicit-token"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert r.status_code == 401
    assert r.json()["detail"] == "Refresh token required"
    assert "Refresh token rejected reason=missing_cookie" in caplog.text


def test_refresh_logs_invalid_cookie_reason_without_token_value(auth_client, caplog):
    caplog.set_level(logging.INFO, logger=auth_module.__name__)
    auth_client.cookies.set("refresh_token", "dummy-refresh-token")
    with patch.object(auth_module.AuthService, "validate_refresh_token") as validate_refresh_token:
        validate_refresh_token.return_value = {
            "valid": False,
            "user_id": 42,
            "jti": "old-jti",
            "family_id": "family-1",
            "error": "token_reused",
        }
        r = auth_client.post(
            "/api/v1/auth/refresh",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert r.status_code == 401
    assert r.json()["detail"] == "Refresh token has already been used"
    assert "Refresh token rejected reason=token_reused" in caplog.text
    assert "user_id=42" in caplog.text
    assert "jti=old-jti" in caplog.text
    assert "family_id=family-1" in caplog.text
    assert "dummy-refresh-token" not in caplog.text


def test_refresh_requires_csrf_header_for_valid_cookie(auth_client):
    auth_client.cookies.set("refresh_token", "dummy-refresh-token")
    with patch.object(auth_module.AuthService, "validate_refresh_token") as validate_refresh_token:
        validate_refresh_token.return_value = {
            "valid": True,
            "user_id": 42,
            "jti": "old-jti",
            "family_id": "family-1",
            "csrf_token": "csrf-old",
            "idle_expires_in": 1800,
        }
        r = auth_client.post(
            "/api/v1/auth/refresh",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert r.status_code == 403
    assert r.json()["detail"] == "Invalid CSRF token"


def test_refresh_accepts_matching_csrf_and_rotates_cookie(auth_client):
    auth_client.cookies.set("refresh_token", "dummy-refresh-token")
    with (
        patch.object(auth_module.AuthService, "validate_refresh_token") as validate_refresh_token,
        patch.object(auth_module.AuthService, "rotate_refresh_token") as rotate_refresh_token,
    ):
        validate_refresh_token.return_value = {
            "valid": True,
            "user_id": 42,
            "jti": "old-jti",
            "family_id": "family-1",
            "csrf_token": "csrf-old",
            "idle_expires_in": 1800,
        }
        rotate_refresh_token.return_value = {
            "access_token": "access-token",
            "refresh_token": "refresh-token-new",
            "csrf_token": "csrf-new",
            "expires_in": 900,
            "refresh_max_age": 3600,
            "idle_expires_in": 1800,
        }
        r = auth_client.post(
            "/api/v1/auth/refresh",
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRF-Token": "csrf-old",
            },
        )

    assert r.status_code == 200
    assert r.json()["access_token"] == "access-token"
    set_cookie = r.headers.get("set-cookie", "")
    assert "refresh_token=refresh-token-new" in set_cookie
    assert "csrf_token=csrf-new" in set_cookie


def test_activity_requires_ajax_header_before_auth(auth_client):
    r = auth_client.post("/api/v1/auth/activity")

    assert r.status_code == 403
    assert r.json()["detail"] == "Missing required auth request header"
