"""Tests for BulletinBoardService."""

from __future__ import annotations

import sys
from unittest.mock import patch

project_root = __import__("pathlib").Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.services.bulletin_board import BulletinBoardService  # noqa: E402


def test_render_notice_md_to_terminal_strips():
    svc = BulletinBoardService()
    assert svc.render_notice_md_to_terminal("  hello  ") == "hello"
    assert svc.render_notice_md_to_terminal("") == ""


@patch.object(BulletinBoardService, "_with_board")
def test_list_notices_empty_when_no_board(mock_wb):
    mock_wb.return_value = None
    svc = BulletinBoardService()
    out = svc.list_notices(page=3, page_size=10)
    assert out["items"] == []
    assert out["total"] == 0
    assert out["page"] == 3
