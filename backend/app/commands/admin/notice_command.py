"""
Notice admin command for system bulletin board.
"""
from __future__ import annotations
from typing import List, Optional
from ..base import AdminCommand, CommandContext, CommandResult
from app.services.bulletin_board import bulletin_board_service


class NoticeCommand(AdminCommand):
    """Admin operations: notice publish/edit/archive/list/view."""

    def __init__(self):
        super().__init__(name='notice', description='管理系统公告(publish/edit/archive/list/view)', aliases=['notices'])

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result('用法: notice <publish|edit|archive|list|view> ...')
        action = str(args[0]).lower()
        rest = args[1:]
        if action == 'publish':
            return self._publish(context, rest)
        if action == 'edit':
            return self._edit(context, rest)
        if action == 'archive':
            return self._archive(context, rest)
        if action == 'list':
            return self._list(context, rest)
        if action == 'view':
            return self._view(context, rest)
        return CommandResult.error_result(f'未知操作: {action}')

    def _publish(self, context: CommandContext, args: List[str]) -> CommandResult:
        """
        notice publish <title> | <content_md>
        """
        payload = ' '.join(args).strip()
        if '|' not in payload:
            return CommandResult.error_result('用法: notice publish <title> | <content_md>')
        (title, content) = [p.strip() for p in payload.split('|', 1)]
        if not title or not content:
            return CommandResult.error_result('标题和正文不能为空')
        dto = bulletin_board_service.publish_notice(title, content, author_id=self._safe_int(context.user_id))
        if not dto:
            return CommandResult.error_result('公告发布失败')
        return CommandResult.success_result(f"公告已发布: #{dto.get('id')} {dto.get('title')}")

    def _edit(self, context: CommandContext, args: List[str]) -> CommandResult:
        """
        notice edit <id> <title>|<content_md>
        """
        if len(args) < 2:
            return CommandResult.error_result('用法: notice edit <id> <title> | <content_md>')
        notice_id = self._safe_int(args[0])
        if not notice_id:
            return CommandResult.error_result('无效 notice id')
        payload = ' '.join(args[1:]).strip()
        if '|' not in payload:
            return CommandResult.error_result('用法: notice edit <id> <title> | <content_md>')
        (title, content) = [p.strip() for p in payload.split('|', 1)]
        dto = bulletin_board_service.edit_notice(notice_id, title=title or None, content_md=content or None, editor_id=self._safe_int(context.user_id))
        if not dto:
            return CommandResult.error_result(f'公告编辑失败: {notice_id}')
        return CommandResult.success_result(f'公告已更新: #{notice_id}')

    def _archive(self, context: CommandContext, args: List[str]) -> CommandResult:
        """notice archive <id>"""
        if not args:
            return CommandResult.error_result('用法: notice archive <id>')
        notice_id = self._safe_int(args[0])
        if not notice_id:
            return CommandResult.error_result('无效 notice id')
        dto = bulletin_board_service.archive_notice(notice_id, editor_id=self._safe_int(context.user_id))
        if not dto:
            return CommandResult.error_result(f'公告归档失败: {notice_id}')
        return CommandResult.success_result(f'公告已归档: #{notice_id}')

    def _list(self, context: CommandContext, args: List[str]) -> CommandResult:
        """
        notice list [status] [page]
        status: published|draft|archived|all
        """
        status: Optional[str] = None
        page = 1
        if args:
            status = str(args[0]).lower()
            if status not in ('published', 'draft', 'archived', 'all'):
                return CommandResult.error_result('status 仅支持 all|published|draft|archived')
        if len(args) > 1:
            page = self._safe_int(args[1]) or 1
        data = bulletin_board_service.admin_list_notices(status=None if status in (None, 'all') else status, include_inactive=True, page=page, page_size=10)
        items = data.get('items') or []
        lines = [f"notices page {data.get('page', 1)}/{data.get('total_pages', 1)} (total={data.get('total', 0)})", '']
        if not items:
            lines.append('No notices.')
        else:
            for it in items:
                lines.append(f"#{it.get('id')} [{it.get('status', 'unknown')}] {it.get('title', 'Untitled')}")
        return CommandResult.success_result('\n'.join(lines).strip())

    def _view(self, context: CommandContext, args: List[str]) -> CommandResult:
        """
        notice view <id>
        """
        from app.commands.i18n.locale_text import resolve_locale
        from app.commands.i18n.command_resource import get_command_i18n_text

        loc = resolve_locale(context)

        if not args:
            return CommandResult.error_result(
                get_command_i18n_text("notice", "view.error.usage", loc, "用法: notice view <id>")
            )

        notice_id = self._safe_int(args[0])
        if not notice_id:
            return CommandResult.error_result(
                get_command_i18n_text("notice", "view.error.invalid_id", loc, "无效公告 ID")
            )

        dto = bulletin_board_service.get_notice_by_id(notice_id, public_only=False)
        if not dto:
            return CommandResult.error_result(
                get_command_i18n_text("notice", "view.error.not_found", loc, "公告不存在: #{id}").format(id=notice_id)
            )

        title = dto.get('title', '')
        content_md = dto.get('content_md', '')
        status = dto.get('status', '')
        author_id = dto.get('author_id')
        # author 存储为 ID，需要查询数据库获取用户名
        author = 'unknown'
        if author_id and context.db_session:
            try:
                from app.models.graph import Node
                user_node = context.db_session.query(Node).filter(
                    Node.id == author_id,
                    Node.type_code == 'account',
                    Node.is_active == True
                ).first()
                if user_node:
                    author = user_node.name or str(author_id)
                else:
                    author = str(author_id)
            except Exception:
                author = str(author_id) if author_id else 'unknown'
        elif author_id:
            author = str(author_id)
        created_at = dto.get('published_at') or dto.get('created_at', '')

        # 渲染 markdown 正文为终端安全文本
        rendered_content = bulletin_board_service.render_notice_md_to_terminal(content_md)

        # 分块输出（防止超长公告刷屏）
        chunks = bulletin_board_service.split_terminal_chunks(rendered_content)

        # 构建输出
        header = get_command_i18n_text("notice", "view.header", loc, "公告详情")
        lines = [
            header,
            "=" * 40,
            f"#{notice_id} [{status}] {title}",
            f"{get_command_i18n_text('notice', 'view.author', loc, '作者')}: {author}",
            f"{get_command_i18n_text('notice', 'view.time', loc, '时间')}: {created_at}",
            "-" * 40,
        ]

        for chunk in chunks:
            lines.append(chunk)

        return CommandResult.success_result('\n'.join(lines))

    @staticmethod
    def _safe_int(v) -> Optional[int]:
        try:
            return int(v)
        except Exception:
            return None
