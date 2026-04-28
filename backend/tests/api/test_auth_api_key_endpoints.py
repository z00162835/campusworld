import sys
from pathlib import Path
from unittest.mock import MagicMock
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.api.v1.dependencies import AuthenticatedUser
from app.api.v1.endpoints import auth as auth_module
from app.models.graph import Node
from app.models.system import ApiKey


def _build_client(mock_account, api_key_rows=None):
    app = FastAPI()
    app.include_router(auth_module.router, prefix="/api/v1/auth")

    mock_db = MagicMock()
    api_key_rows = api_key_rows or []

    def _query(model):
        q = MagicMock()
        if model is Node:
            q.filter.return_value.first.return_value = mock_account
        elif model is ApiKey:
            q.filter.return_value.order_by.return_value.all.return_value = api_key_rows
            q.filter.return_value.all.return_value = api_key_rows
        return q

    mock_db.query.side_effect = _query

    def _mock_get_db():
        yield mock_db

    async def _mock_current_user():
        return AuthenticatedUser(
            user_id="42",
            username="alice",
            email="alice@example.com",
            roles=["player"],
            permissions=[],
            user_attrs={},
        )

    app.dependency_overrides[auth_module.get_db] = _mock_get_db
    app.dependency_overrides[auth_module.get_current_http_user] = _mock_current_user
    return TestClient(app, raise_server_exceptions=False), mock_db


def test_issue_api_key_returns_segmented_key(monkeypatch):
    account = MagicMock(spec=Node)
    account.id = 42
    account.type_code = "account"
    account.attributes = {"email": "alice@example.com"}

    monkeypatch.setattr(
        auth_module,
        "build_api_key_record",
        lambda: ("cwk_ab12cd34ef56ab78_deadbeef" * 3, "ab12cd34ef56ab78", "salt1", 210000, "hash1"),
    )

    client, mock_db = _build_client(account)
    response = client.post(
        "/api/v1/auth/api-key",
        json={"name": "ci-agent", "scopes": ["graph.read"], "expires_in_days": 30},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["api_key"].startswith("cwk_ab12cd34ef56ab78_")
    assert body["kid"] == "ab12cd34ef56ab78"
    assert body["expires_at"] is not None
    assert body["created_at"] is not None
    mock_db.commit.assert_called()


def test_rotate_api_key_replaces_existing_key():
    account = MagicMock(spec=Node)
    account.id = 42
    account.type_code = "account"
    account.attributes = {}

    old_key = MagicMock(spec=ApiKey)
    old_key.kid = "oldkid"
    old_key.revoked = False
    old_key.revoked_at = None

    client, mock_db = _build_client(account, api_key_rows=[old_key])
    response = client.post(
        "/api/v1/auth/api-key/rotate",
        json={"name": "rotated", "scopes": ["graph.write"], "expires_in_days": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["api_key"].startswith("cwk_")
    assert body["rotated_count"] == 1
    assert body["expires_at"] is not None
    assert old_key.revoked is True
    assert old_key.revoked_at is not None
    mock_db.commit.assert_called()


def test_list_api_keys_returns_metadata_only():
    account = MagicMock(spec=Node)
    account.id = 42
    account.type_code = "account"
    account.attributes = {}

    row = MagicMock(spec=ApiKey)
    row.kid = "kid01"
    row.name = "agent-key"
    row.algorithm = "pbkdf2_sha256"
    row.iterations = 210000
    row.revoked = False
    row.created_at = datetime.utcnow()
    row.expires_at = None
    row.last_used_at = None

    client, _mock_db = _build_client(account, api_key_rows=[row])
    response = client.get("/api/v1/auth/api-key")

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["kid"] == "kid01"
    assert "api_key" not in body["items"][0]
