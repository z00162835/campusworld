"""
Bulletin board read API for SSH / game commands.

Delegates persistence rules to :class:`SystemBulletinManager`.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

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

    def render_notice_md_to_terminal(self, content_md: str) -> str:
        """
        Terminal-safe body text. Full Markdown sanitization is phase 4.

        On render errors this will still return stripped plain text.
        """
        try:
            return (content_md or "").strip()
        except Exception as e:
            logger.warning("render_notice_md_to_terminal degraded: %s", e)
            return str(content_md or "")

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


# Shared default for convenience (commands may import this).
bulletin_board_service = BulletinBoardService()
