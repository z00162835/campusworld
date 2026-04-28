"""Unit tests for data_access policy helpers (no DB)."""

from unittest.mock import MagicMock

from app.constants.data_access_defaults import ADMIN_DATA_ACCESS, USER_LIKE_DATA_ACCESS
from app.schemas.data_access import DataAccessV1, parse_data_access
from app.services.data_access_policy import (
    load_policy,
    node_row_visible,
    proposed_node_visible,
)


def _node(type_code: str, wid, nid: int = 1) -> MagicMock:
    n = MagicMock()
    n.type_code = type_code
    n.id = nid
    n.attributes = {"world_id": wid} if wid is not None else {}
    return n


def test_parse_missing_returns_none():
    assert parse_data_access(None) is None
    assert parse_data_access({}) is None


def test_load_policy_deny_all_when_missing():
    pol, deny = load_policy({})
    assert pol is None
    assert deny is True


def test_admin_template_allows_room_with_world():
    pol, deny = load_policy({"data_access": ADMIN_DATA_ACCESS})
    assert deny is False
    assert pol is not None
    row = _node("room", "42", 10)
    assert node_row_visible(row, pol, deny) is True


def test_user_like_denies_account():
    pol, deny = load_policy({"data_access": USER_LIKE_DATA_ACCESS})
    assert deny is False
    acc = _node("account", None, 99)
    assert node_row_visible(acc, pol, deny) is False


def test_user_like_denies_node_without_world_id():
    pol, deny = load_policy({"data_access": USER_LIKE_DATA_ACCESS})
    row = _node("room", None, 5)
    assert node_row_visible(row, pol, deny) is False


def test_user_like_allows_room_in_world():
    pol, deny = load_policy({"data_access": USER_LIKE_DATA_ACCESS})
    row = _node("room", "7", 5)
    assert node_row_visible(row, pol, deny) is True


def test_proposed_create_denies_account_for_user_like():
    pol, deny = load_policy({"data_access": USER_LIKE_DATA_ACCESS})
    assert proposed_node_visible("account", {"world_id": "1"}, pol, deny) is False


def test_denied_type_codes_in_schema():
    raw = {
        "version": 1,
        "permission_template": {
            "world_ids": [],
            "type_codes": [],
            "relationships_codes": [],
            "node_ids": [],
            "exclude_nodes_without_world_id": False,
        },
        "denied_type_codes": ["account"],
        "denied_world_ids": [],
        "denied_relationships_codes": [],
        "denied_nodes": [],
    }
    p = DataAccessV1.model_validate(raw)
    assert "account" in p.denied_type_codes
