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


def test_render_notice_md_to_terminal_sanitizes_markdown_and_html():
    svc = BulletinBoardService()
    text = svc.render_notice_md_to_terminal(
        "# Title\n"
        "<script>alert('x')</script>\n"
        "normal [link](https://example.com) and `code` and **bold**"
    )
    assert "Title" in text
    assert "alert" not in text
    assert "link" in text
    assert "https://example.com" in text
    assert "code" in text
    assert "**" not in text


def test_render_notice_md_to_terminal_chunks_long_text():
    svc = BulletinBoardService()
    long_text = "\n".join([f"line-{i}" for i in range(300)])
    chunks = svc.render_notice_md_to_terminal_chunks(long_text, max_chars=200)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)


@patch.object(BulletinBoardService, "_with_board")
def test_admin_notice_methods_forward_to_manager(mock_wb):
    svc = BulletinBoardService()
    mock_wb.return_value = {"id": 1, "title": "n1"}
    out = svc.edit_notice(1, title="t")
    assert out["id"] == 1
    out2 = svc.archive_notice(1)
    assert out2["id"] == 1


@patch.object(BulletinBoardService, "_with_board")
def test_list_notices_empty_when_no_board(mock_wb):
    mock_wb.return_value = None
    svc = BulletinBoardService()
    out = svc.list_notices(page=3, page_size=10)
    assert out["items"] == []
    assert out["total"] == 0
    assert out["page"] == 3
