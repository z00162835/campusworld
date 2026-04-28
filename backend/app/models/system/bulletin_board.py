"""
System bulletin board object.

This object represents the singleton board placed in SingularityRoom.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.models.base import DefaultObject
from app.core.log import get_logger, LoggerNames


class BulletinBoard(DefaultObject):
    """System singleton bulletin board object."""

    DEFAULT_BOARD_KEY = "system_bulletin_board"
    _MODE_ALIASES = {
        "next": "next",
        "n": "next",
        "prev": "prev",
        "p": "prev",
        "previous": "prev",
    }
    _LOOK_ALIASES = ["bulletin_board", "bulletin", "board"]
    _logger = get_logger(LoggerNames.GAME)

    def room_line_format_kwargs(self):
        kw = super().room_line_format_kwargs()
        a = self._node_attributes
        blurb = str(a.get("short_blurb") or a.get("desc") or "").strip()[:200]
        kw["short_blurb"] = blurb
        if blurb:
            sep = " — " if (kw.get("hints") or "").strip() else " "
            kw["hints"] = (kw.get("hints") or "") + sep + blurb
        return kw

    def __init__(self, name: str = "bulletin_board", config: Optional[Dict[str, Any]] = None, **kwargs):
        self._node_type = "system_bulletin_board"

        attrs = {
            "board_key": self.DEFAULT_BOARD_KEY,
            "display_name": "bulletin_board",
            "desc": "System bulletin board in SingularityRoom",
            "entry_room": "singularity_room",
            "entity_kind": "item",
            "presentation_domains": ["room"],
            "access_locks": {"view": "all()", "interact": "all()"},
            "is_system_singleton": True,
            "supports_markdown_notice": True,
            "aliases": list(self._LOOK_ALIASES),
            "created_at": datetime.now().isoformat(),
        }
        if config and "attributes" in config:
            attrs.update(config["attributes"])
        attrs.update(kwargs)

        tags = ["system", "bulletin_board", "singleton", "bulletin", "board"]
        if config and "tags" in config:
            tags.extend(config["tags"])

        super().__init__(
            name=name,
            attributes=attrs,
            tags=list(dict.fromkeys(tags)),
            disable_auto_sync=bool(kwargs.get("disable_auto_sync", False)),
            is_public=True,
            access_level="normal",
        )

    def get_display_name(self) -> str:
        return self.get_attribute("display_name", "bulletin_board")

    def _get_ctx_page_key(self) -> str:
        return "bulletin_board.page"

    def _get_ctx_page(self, context: Any) -> int:
        try:
            if not context:
                return 1
            if not getattr(context, "metadata", None):
                context.metadata = {}
            v = context.metadata.get(self._get_ctx_page_key(), 1)
            v = int(v)
            return v if v >= 1 else 1
        except Exception:
            return 1

    def _set_ctx_page(self, context: Any, page: int) -> None:
        try:
            if not context:
                return
            if not getattr(context, "metadata", None):
                context.metadata = {}
            context.metadata[self._get_ctx_page_key()] = int(page)
        except Exception:
            return

    def _parse_appearance_args(self, args: Optional[List[str]]) -> Tuple[str, Dict[str, Any]]:
        """
        Parse sub-args for appearance.

        Supported:
        - [] -> list (page=1)
        - ["next"|"prev"] -> paginate
        - ["page", N] -> list page N
        - [INDEX] -> detail by page index (1..N)
        - ["id", NOTICE_ID] -> detail by id
        """
        args = args or []
        if not args:
            return "list", {}

        a0 = str(args[0]).lower()
        alias_mode = self._MODE_ALIASES.get(a0)
        if alias_mode:
            return alias_mode, {}
        if a0 == "page" and len(args) >= 2:
            try:
                page = int(args[1])
            except (TypeError, ValueError):
                return "error", {"reason": "invalid_page"}
            return "list", {"page": max(1, page)}
        if a0 == "id" and len(args) >= 2:
            try:
                notice_id = int(args[1])
            except (TypeError, ValueError):
                return "error", {"reason": "invalid_notice_id"}
            return "id", {"id": notice_id}

        # index detail
        try:
            return "index", {"index": int(args[0])}
        except (TypeError, ValueError):
            return "list", {}

    def get_appearance(self, context=None, args: Optional[List[str]] = None) -> str:
        from app.services.bulletin_board import BulletinBoardService

        service = BulletinBoardService()
        mode, payload = self._parse_appearance_args(args)

        page = self._get_ctx_page(context)
        if mode == "error":
            reason = payload.get("reason")
            if reason == "invalid_page":
                return "Invalid page number. Usage: look bulletin_board page <n>"
            if reason == "invalid_notice_id":
                return "Invalid notice id. Usage: look bulletin_board id <notice_id>"
            return "Invalid bulletin_board command arguments."

        if mode == "list":
            page = int(payload.get("page", page or 1))
            if page < 1:
                page = 1
            self._set_ctx_page(context, page)
            data = service.list_notices(page=page, page_size=10)
            return self._render_list_view(data)

        if mode == "next":
            page = page + 1
            self._set_ctx_page(context, page)
            data = service.list_notices(page=page, page_size=10)
            # service clamps to last page; sync it back
            self._set_ctx_page(context, int(data.get("page", page)))
            return self._render_list_view(data)

        if mode == "prev":
            page = max(1, page - 1)
            self._set_ctx_page(context, page)
            data = service.list_notices(page=page, page_size=10)
            self._set_ctx_page(context, int(data.get("page", page)))
            return self._render_list_view(data)

        if mode == "id":
            notice_id = payload.get("id")
            if not notice_id:
                return "Invalid notice id."
            notice = service.get_notice_by_id(int(notice_id), public_only=True)
            if not notice:
                return f"Notice not found: {notice_id}"
            body_chunks = service.render_notice_md_to_terminal_chunks(notice.get("content_md", ""))
            return self._render_detail_view(notice, body_chunks)

        if mode == "index":
            index = payload.get("index")
            if not index or int(index) < 1:
                return "Invalid notice index."
            notice = service.get_notice_by_page_index(page=page, index=int(index), page_size=10)
            if not notice:
                return f"Notice not found on page {page}: {index}"
            body_chunks = service.render_notice_md_to_terminal_chunks(notice.get("content_md", ""))
            return self._render_detail_view(notice, body_chunks)

        data = service.list_notices(page=page, page_size=10)
        return self._render_list_view(data)

    def _render_list_view(self, data: Dict[str, Any]) -> str:
        items = data.get("items") or []
        page = int(data.get("page", 1) or 1)
        total_pages = int(data.get("total_pages", 1) or 1)

        lines = ["bulletin_board", f"Page {page}/{total_pages}", ""]
        if not items:
            lines.append("No system notices.")
            lines.append("")
            lines.append("Usage: look bulletin_board | look bulletin_board next | look bulletin_board <index>")
            return "\n".join(lines).strip()

        for i, it in enumerate(items, 1):
            title = it.get("title", "Untitled")
            published_at = it.get("published_at") or ""
            suffix = f" ({published_at})" if published_at else ""
            lines.append(f"{i}. {title}{suffix}")

        lines.append("")
        lines.append("Usage: look bulletin_board <index> | look bulletin_board next | look bulletin_board prev | look bulletin_board page <n>")
        return "\n".join(lines).strip()

    def _render_detail_view(self, notice: Dict[str, Any], body_chunks: List[str]) -> str:
        title = notice.get("title", "Untitled")
        published_at = notice.get("published_at") or ""
        header = [title, "-" * len(title)]
        if published_at:
            header.append(f"Published: {published_at}")
        header.append("")
        if not body_chunks:
            header.append("")
        elif len(body_chunks) == 1:
            header.append((body_chunks[0] or "").strip())
        else:
            total = len(body_chunks)
            for i, chunk in enumerate(body_chunks, 1):
                header.append(f"[Part {i}/{total}]")
                header.append((chunk or "").strip())
                if i < total:
                    header.append("")
        header.append("")
        header.append("Back: look bulletin_board")
        return "\n".join(header).strip()
