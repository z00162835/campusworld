"""BulletinBoard model appearance integration (no DB)."""

from __future__ import annotations

import sys

project_root = __import__("pathlib").Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class _Ctx:
    def __init__(self):
        self.metadata = {}


def test_bulletin_board_appearance_list_and_detail_without_db(monkeypatch):
    from app.models.system.bulletin_board import BulletinBoard
    from app.services import bulletin_board as bb_mod

    class _FakeSvc:
        def list_notices(self, page: int = 1, page_size: int = 10):
            return {
                "items": [
                    {"id": 1, "title": "t1", "published_at": "2024-01-01T00:00:00"},
                    {"id": 2, "title": "t2", "published_at": "2024-01-02T00:00:00"},
                ],
                "total": 2,
                "total_pages": 1,
                "page": 1,
                "page_size": 10,
            }

        def get_notice_by_page_index(self, page: int, index: int, page_size: int = 10):
            if index == 1:
                return {"id": 1, "title": "t1", "content_md": "# hi", "published_at": "2024-01-01T00:00:00"}
            return None

        def get_notice_by_id(self, notice_id: int, *, public_only: bool = True):
            if notice_id == 2:
                return {"id": 2, "title": "t2", "content_md": "body", "published_at": None}
            return None

        def render_notice_md_to_terminal(self, content_md: str) -> str:
            return content_md

    monkeypatch.setattr(bb_mod, "BulletinBoardService", lambda: _FakeSvc())

    board = BulletinBoard(disable_auto_sync=True)
    ctx = _Ctx()

    text = board.get_appearance(context=ctx, args=[])
    assert "Page 1/1" in text
    assert "1. t1" in text

    detail = board.get_appearance(context=ctx, args=["1"])
    assert "t1" in detail
    assert "# hi" in detail

    detail2 = board.get_appearance(context=ctx, args=["id", "2"])
    assert "t2" in detail2
    assert "body" in detail2
