"""Unit tests for SystemBulletinManager."""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

project_root = __import__("pathlib").Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.services.system_bulletin_manager import (  # noqa: E402
    SystemBulletinManager,
    _is_public_list_notice,
    validate_notice_title,
    validate_notice_content,
)


def _node(**kwargs):
    defaults = dict(
        id=1,
        uuid=uuid.uuid4(),
        name="n",
        attributes={},
        created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        location_id=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_is_public_list_notice_requires_published_and_active():
    assert _is_public_list_notice(_node(attributes={"status": "published", "is_active": True}))
    assert not _is_public_list_notice(_node(attributes={"status": "draft", "is_active": True}))
    assert not _is_public_list_notice(_node(attributes={"status": "published", "is_active": False}))
    assert _is_public_list_notice(_node(attributes={"status": "published"}))


def test_validate_notice_title():
    assert validate_notice_title("ok")[0]
    assert not validate_notice_title("")[0]
    assert not validate_notice_title("x" * 121)[0]


def test_validate_notice_content():
    assert validate_notice_content("hello")[0]
    assert not validate_notice_content("  ")[0]
    assert not validate_notice_content(None)[0]


@patch.object(SystemBulletinManager, "_fetch_published_notice_candidates")
def test_list_published_notices_sort_and_pagination(mock_fetch):
    mock_fetch.return_value = [
        _node(
            id=1,
            attributes={"title": "b", "status": "published", "published_at": "2024-01-02T00:00:00"},
            created_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        ),
        _node(
            id=2,
            attributes={"title": "a", "status": "published", "published_at": "2024-06-01T00:00:00"},
            created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        ),
    ]
    mgr = SystemBulletinManager()
    session = MagicMock()
    out = mgr.list_published_notices(session, board_node_id=10, page=1, page_size=1)
    assert out["total"] == 2
    assert out["total_pages"] == 2
    assert len(out["items"]) == 1
    assert out["items"][0]["title"] == "a"
    out2 = mgr.list_published_notices(session, board_node_id=10, page=2, page_size=1)
    assert out2["items"][0]["title"] == "b"


@patch.object(SystemBulletinManager, "_fetch_published_notice_candidates")
def test_get_notice_by_page_index(mock_fetch):
    n = _node(
        id=42,
        location_id=10,
        attributes={
            "title": "full",
            "status": "published",
            "published_at": "2024-01-01T00:00:00",
            "content_md": "# Hi",
        },
    )
    mock_fetch.return_value = [n]
    mgr = SystemBulletinManager()
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = n
    dto = mgr.get_notice_by_page_index(session, 10, page=1, index=1, page_size=10)
    assert dto is not None
    assert dto["id"] == 42
    assert dto["content_md"] == "# Hi"
