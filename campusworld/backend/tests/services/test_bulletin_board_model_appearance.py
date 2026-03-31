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

        def render_notice_md_to_terminal_chunks(self, content_md: str, max_chars: int = 1200):
            return [content_md]

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


def test_bulletin_board_appearance_arg_validation_and_aliases(monkeypatch):
    from app.models.system.bulletin_board import BulletinBoard
    from app.services import bulletin_board as bb_mod

    class _FakeSvc:
        def list_notices(self, page: int = 1, page_size: int = 10):
            return {
                "items": [{"id": 1, "title": "only", "published_at": None}],
                "total": 1,
                "total_pages": 1,
                "page": 1,
                "page_size": 10,
            }

        def get_notice_by_page_index(self, page: int, index: int, page_size: int = 10):
            return None

        def get_notice_by_id(self, notice_id: int, *, public_only: bool = True):
            return None

        def render_notice_md_to_terminal(self, content_md: str) -> str:
            return content_md
        
        def render_notice_md_to_terminal_chunks(self, content_md: str, max_chars: int = 1200):
            return [content_md]

    monkeypatch.setattr(bb_mod, "BulletinBoardService", lambda: _FakeSvc())

    board = BulletinBoard(disable_auto_sync=True)
    ctx = _Ctx()

    # alias parsing
    out_next = board.get_appearance(context=ctx, args=["n"])
    assert "Page 1/1" in out_next
    out_prev = board.get_appearance(context=ctx, args=["previous"])
    assert "Page 1/1" in out_prev

    # explicit parse errors
    out_bad_page = board.get_appearance(context=ctx, args=["page", "abc"])
    assert "Invalid page number" in out_bad_page

    out_bad_id = board.get_appearance(context=ctx, args=["id", "oops"])
    assert "Invalid notice id" in out_bad_id


def test_bulletin_board_has_explicit_lookup_aliases():
    from app.models.system.bulletin_board import BulletinBoard

    board = BulletinBoard(disable_auto_sync=True)
    attrs = board.get_node_attributes()
    aliases = attrs.get("aliases", [])
    assert "bulletin" in aliases
    assert "board" in aliases
    tags = board.get_node_tags()
    assert "bulletin" in tags
    assert "board" in tags


def test_bulletin_board_page_state_persists_in_context_metadata(monkeypatch):
    from app.models.system.bulletin_board import BulletinBoard
    from app.services import bulletin_board as bb_mod

    class _FakeSvc:
        def list_notices(self, page: int = 1, page_size: int = 10):
            return {
                "items": [{"id": page, "title": f"p{page}", "published_at": None}],
                "total": 20,
                "total_pages": 20,
                "page": page,
                "page_size": page_size,
            }

        def get_notice_by_page_index(self, page: int, index: int, page_size: int = 10):
            return None

        def get_notice_by_id(self, notice_id: int, *, public_only: bool = True):
            return None

        def render_notice_md_to_terminal_chunks(self, content_md: str, max_chars: int = 1200):
            return [content_md]

    monkeypatch.setattr(bb_mod, "BulletinBoardService", lambda: _FakeSvc())

    board = BulletinBoard(disable_auto_sync=True)
    ctx = _Ctx()
    t1 = board.get_appearance(context=ctx, args=[])
    assert "Page 1/20" in t1
    t2 = board.get_appearance(context=ctx, args=["next"])
    assert "Page 2/20" in t2
    assert ctx.metadata.get("bulletin_board.page") == 2
