"""
Bulletin board read API for SSH / game commands.

Delegates persistence rules to :class:`SystemBulletinManager`.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.core.database import db_session_context
from app.core.log import get_logger, LoggerNames

from .system_bulletin_manager import SystemBulletinManager

if TYPE_CHECKING:
    from app.models.root_manager import RootNodeManager

logger = get_logger(LoggerNames.GAME)


class BulletinBoardService:
    """
    High-level operations for the singleton board in SingularityRoom.

    Resolves the board via :attr:`root_manager` and performs queries in
    ``db_session_context`` so callers do not manage sessions.
    """

    def __init__(
        self,
        root_manager: Optional["RootNodeManager"] = None,
        bulletin_manager: Optional[SystemBulletinManager] = None,
    ):
        if root_manager is None:
            from app.models.root_manager import root_manager as default_root

            root_manager = default_root
        self._roots = root_manager
        self._mgr = bulletin_manager or SystemBulletinManager()

    _MAX_OUTPUT_CHARS = 1200

    def _strip_html_tags(self, text: str) -> str:
        """Best-effort HTML/script strip for terminal-safe output."""
        # Drop script/style blocks first, then remove remaining tags.
        no_script = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", text, flags=re.IGNORECASE | re.DOTALL)
        no_tags = re.sub(r"<[^>]+>", "", no_script)
        return no_tags

    def _markdown_to_terminal_text(self, content_md: str) -> str:
        """Convert markdown-ish content to plain terminal text safely."""
        text = str(content_md or "")
        text = self._strip_html_tags(text)
        # fenced code blocks -> keep code body only
        text = re.sub(r"```[a-zA-Z0-9_-]*\n?", "", text)
        # inline code
        text = re.sub(r"`([^`]+)`", r"\1", text)
        # headings
        text = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.MULTILINE)
        # emphasis markers
        text = re.sub(r"(\*\*|__|\*|_)", "", text)
        # links [label](url) -> label
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
        # collapse excessive empty lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def split_terminal_chunks(self, text: str, max_chars: int = _MAX_OUTPUT_CHARS) -> List[str]:
        """Split long output into stable terminal chunks by line boundaries."""
        s = (text or "").strip()
        if not s:
            return [""]
        if len(s) <= max_chars:
            return [s]

        chunks: List[str] = []
        current: List[str] = []
        current_len = 0
        for line in s.splitlines():
            ln = len(line) + 1
            if current and current_len + ln > max_chars:
                chunks.append("\n".join(current).strip())
                current = [line]
                current_len = ln
            else:
                current.append(line)
                current_len += ln
        if current:
            chunks.append("\n".join(current).strip())
        return chunks or [s]

    def render_notice_md_to_terminal(self, content_md: str) -> str:
        """
        Terminal-safe body text from markdown.
        On render errors this degrades to plain stripped text.
        """
        try:
            return self._markdown_to_terminal_text(content_md)
        except Exception as e:
            logger.warning("bulletin_render_degraded error_type=%s", type(e).__name__)
            return str(content_md or "")

    def render_notice_md_to_terminal_chunks(self, content_md: str, max_chars: int = _MAX_OUTPUT_CHARS) -> List[str]:
        """Render markdown and split long body for stable terminal output."""
        rendered = self.render_notice_md_to_terminal(content_md)
        return self.split_terminal_chunks(rendered, max_chars=max_chars)

    def _with_board(
        self,
        fn,
    ) -> Any:
        """Run callback(session, board_node_id) or return None if board missing."""

        def runner():
            try:
                with db_session_context() as session:
                    root = self._roots.get_root_node(session)
                    if not root:
                        return None
                    board_id = self._mgr.resolve_board_node_id(session, root.id)
                    if not board_id:
                        return None
                    return fn(session, board_id)
            except Exception as e:
                logger.error("BulletinBoardService operation failed: %s", e)
                return None

        return runner()

    def list_notices(self, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        result = self._with_board(
            lambda session, board_id: self._mgr.list_published_notices(
                session, board_id, page=page, page_size=page_size
            )
        )
        if result is None:
            return {
                "items": [],
                "total": 0,
                "total_pages": 1,
                "page": max(1, page),
                "page_size": page_size,
            }
        return result

    def get_notice_by_page_index(
        self,
        page: int,
        index: int,
        page_size: int = 10,
    ) -> Optional[Dict[str, Any]]:
        got = self._with_board(
            lambda session, board_id: self._mgr.get_notice_by_page_index(
                session, board_id, page, index, page_size=page_size
            )
        )
        return got

    def get_notice_by_id(self, notice_id: int, *, public_only: bool = True) -> Optional[Dict[str, Any]]:
        got = self._with_board(
            lambda session, board_id: self._mgr.get_notice_by_id(
                session,
                notice_id,
                board_node_id=board_id,
                public_only=public_only,
            )
        )
        return got

    def admin_list_notices(
        self,
        *,
        status: Optional[str] = None,
        include_inactive: bool = True,
        page: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        got = self._with_board(
            lambda session, board_id: self._mgr.list_notices(
                session,
                board_id,
                include_inactive=include_inactive,
                status=status,
                page=page,
                page_size=page_size,
            )
        )
        if got is None:
            return {"items": [], "total": 0, "total_pages": 1, "page": max(1, page), "page_size": page_size}
        return got

    def publish_notice(self, title: str, content_md: str, *, author_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        node = self._with_board(
            lambda session, board_id: self._mgr.create_notice(
                session,
                board_id,
                title,
                content_md,
                status="published",
                author_id=author_id,
            )
        )
        if not node:
            return None
        # node may be SQLAlchemy Node object from create_notice
        notice_id = getattr(node, "id", None)
        if notice_id is None:
            return None
        return self.get_notice_by_id(int(notice_id), public_only=False)

    def edit_notice(
        self,
        notice_id: int,
        *,
        title: Optional[str] = None,
        content_md: Optional[str] = None,
        editor_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        return self._with_board(
            lambda session, board_id: self._mgr.update_notice(
                session,
                notice_id,
                board_node_id=board_id,
                title=title,
                content_md=content_md,
                editor_id=editor_id,
            )
        )

    def archive_notice(self, notice_id: int, *, editor_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        return self._with_board(
            lambda session, board_id: self._mgr.archive_notice(
                session,
                notice_id,
                board_node_id=board_id,
                editor_id=editor_id,
            )
        )


# Shared default for convenience (commands may import this).
bulletin_board_service = BulletinBoardService()
