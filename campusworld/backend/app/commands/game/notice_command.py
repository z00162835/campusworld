"""
Notice admin command for system bulletin board.
"""

from __future__ import annotations

from typing import List, Optional

from ..base import GameCommand, CommandContext, CommandResult
from app.services.bulletin_board import bulletin_board_service


class NoticeCommand(GameCommand):
    """Admin operations: notice publish/edit/archive/list."""

    def __init__(self):
        super().__init__(
            name="notice",
            description="管理系统公告（publish/edit/archive/list）",
            aliases=["notices"],
            game_name="campus_life",
        )

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result("用法: notice <publish|edit|archive|list> ...")

        action = str(args[0]).lower()
        rest = args[1:]
        if action == "publish":
            return self._publish(context, rest)
        if action == "edit":
            return self._edit(context, rest)
        if action == "archive":
            return self._archive(context, rest)
        if action == "list":
            return self._list(context, rest)
        return CommandResult.error_result(f"未知操作: {action}")

    def _publish(self, context: CommandContext, args: List[str]) -> CommandResult:
        """
        notice publish <title> | <content_md>
        """
        payload = " ".join(args).strip()
        if "|" not in payload:
            return CommandResult.error_result("用法: notice publish <title> | <content_md>")
        title, content = [p.strip() for p in payload.split("|", 1)]
        if not title or not content:
            return CommandResult.error_result("标题和正文不能为空")
        dto = bulletin_board_service.publish_notice(title, content, author_id=self._safe_int(context.user_id))
        if not dto:
            return CommandResult.error_result("公告发布失败")
        self.logger.info("AUDIT notice.publish actor=%s notice_id=%s", context.username, dto.get("id"))
        return CommandResult.success_result(f"公告已发布: #{dto.get('id')} {dto.get('title')}")

    def _edit(self, context: CommandContext, args: List[str]) -> CommandResult:
        """
        notice edit <id> <title>|<content_md>
        """
        if len(args) < 2:
            return CommandResult.error_result("用法: notice edit <id> <title> | <content_md>")
        notice_id = self._safe_int(args[0])
        if not notice_id:
            return CommandResult.error_result("无效 notice id")
        payload = " ".join(args[1:]).strip()
        if "|" not in payload:
            return CommandResult.error_result("用法: notice edit <id> <title> | <content_md>")
        title, content = [p.strip() for p in payload.split("|", 1)]
        dto = bulletin_board_service.edit_notice(
            notice_id,
            title=title or None,
            content_md=content or None,
            editor_id=self._safe_int(context.user_id),
        )
        if not dto:
            return CommandResult.error_result(f"公告编辑失败: {notice_id}")
        self.logger.info("AUDIT notice.edit actor=%s notice_id=%s", context.username, notice_id)
        return CommandResult.success_result(f"公告已更新: #{notice_id}")

    def _archive(self, context: CommandContext, args: List[str]) -> CommandResult:
        """notice archive <id>"""
        if not args:
            return CommandResult.error_result("用法: notice archive <id>")
        notice_id = self._safe_int(args[0])
        if not notice_id:
            return CommandResult.error_result("无效 notice id")
        dto = bulletin_board_service.archive_notice(notice_id, editor_id=self._safe_int(context.user_id))
        if not dto:
            return CommandResult.error_result(f"公告归档失败: {notice_id}")
        self.logger.info("AUDIT notice.archive actor=%s notice_id=%s", context.username, notice_id)
        return CommandResult.success_result(f"公告已归档: #{notice_id}")

    def _list(self, context: CommandContext, args: List[str]) -> CommandResult:
        """
        notice list [status] [page]
        status: published|draft|archived|all
        """
        status: Optional[str] = None
        page = 1
        if args:
            a0 = str(args[0]).lower()
            if a0 not in ("all", "published", "draft", "archived"):
                return CommandResult.error_result("status 仅支持 all|published|draft|archived")
            status = None if a0 == "all" else a0
            if len(args) >= 2:
                page = self._safe_int(args[1]) or 1

        payload = bulletin_board_service.admin_list_notices(status=status, include_inactive=True, page=page, page_size=10)
        items = payload.get("items") or []
        lines = [f"notices page {payload.get('page', 1)}/{payload.get('total_pages', 1)} (total={payload.get('total', 0)})", ""]
        if not items:
            lines.append("No notices.")
        else:
            for it in items:
                lines.append(f"#{it.get('id')} [{it.get('status', 'unknown')}] {it.get('title', 'Untitled')}")
        self.logger.info("AUDIT notice.list actor=%s status=%s page=%s", context.username, status or "all", page)
        return CommandResult.success_result("\n".join(lines).strip())

    @staticmethod
    def _safe_int(value) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

