import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.commands.base import CommandContext
from app.commands.base import CommandType
from app.commands.policy import CommandPolicyEvaluator
from app.commands.policy_store import CommandPolicyRepository


def _notice_policy():
    m = MagicMock()
    m.enabled = True
    m.required_permissions_any = ["admin.system_notice"]
    m.required_permissions_all = []
    m.required_roles_any = []
    return m


def _ctx_admin() -> CommandContext:
    return CommandContext(
        user_id="99",
        username="admin",
        session_id="s-admin",
        permissions=["admin.*", "game.hicampus"],
        game_state={"is_running": True, "current_game": "hicampus", "game_info": {}},
        db_session=MagicMock(),
    )


def _ctx_admin_system_notice() -> CommandContext:
    return CommandContext(
        user_id="100",
        username="admin2",
        session_id="s-admin2",
        permissions=["admin.system_notice", "game.hicampus"],
        game_state={"is_running": True, "current_game": "hicampus", "game_info": {}},
        db_session=MagicMock(),
    )


def _ctx_user() -> CommandContext:
    return CommandContext(
        user_id="1",
        username="u1",
        session_id="s-user",
        permissions=["game.hicampus"],
        game_state={"is_running": True, "current_game": "hicampus", "game_info": {}},
        db_session=MagicMock(),
    )


def test_notice_command_denies_non_admin():
    from app.commands.admin.notice_command import NoticeCommand

    cmd = NoticeCommand()
    assert cmd.command_type == CommandType.ADMIN
    with patch.object(CommandPolicyRepository, "get_policy", return_value=_notice_policy()):
        decision = CommandPolicyEvaluator().evaluate(cmd, _ctx_user())
    assert not decision.allowed


def test_notice_command_publish_success(monkeypatch):
    from app.commands.admin.notice_command import NoticeCommand
    from app.commands.admin import notice_command as mod

    monkeypatch.setattr(
        mod.bulletin_board_service,
        "publish_notice",
        lambda title, content_md, author_id=None: {"id": 11, "title": title},
    )

    cmd = NoticeCommand()
    with patch.object(CommandPolicyRepository, "get_policy", return_value=_notice_policy()):
        decision = CommandPolicyEvaluator().evaluate(cmd, _ctx_admin_system_notice())
    assert decision.allowed
    result = cmd.execute(_ctx_admin_system_notice(), ["publish", "Title", "|", "Body"])
    assert result.success
    assert "#11" in result.message


def test_notice_command_edit_archive_and_list(monkeypatch):
    from app.commands.admin.notice_command import NoticeCommand
    from app.commands.admin import notice_command as mod

    monkeypatch.setattr(
        mod.bulletin_board_service,
        "edit_notice",
        lambda notice_id, title=None, content_md=None, editor_id=None: {"id": notice_id, "title": title or "t"},
    )
    monkeypatch.setattr(
        mod.bulletin_board_service,
        "archive_notice",
        lambda notice_id, editor_id=None: {"id": notice_id, "title": "t"},
    )
    monkeypatch.setattr(
        mod.bulletin_board_service,
        "admin_list_notices",
        lambda status=None, include_inactive=True, page=1, page_size=10: {
            "items": [{"id": 1, "status": "published", "title": "n1"}],
            "total": 1,
            "total_pages": 1,
            "page": 1,
            "page_size": 10,
        },
    )

    cmd = NoticeCommand()
    r1 = cmd.execute(_ctx_admin(), ["edit", "1", "New", "|", "Body"])
    assert r1.success
    r2 = cmd.execute(_ctx_admin(), ["archive", "1"])
    assert r2.success
    r3 = cmd.execute(_ctx_admin(), ["list", "all", "1"])
    assert r3.success
    assert "notices page 1/1 (total=1)" in r3.message
    assert "#1 [published] n1" in r3.message


def test_notice_command_list_empty_keeps_pagination_header(monkeypatch):
    from app.commands.admin.notice_command import NoticeCommand
    from app.commands.admin import notice_command as mod

    monkeypatch.setattr(
        mod.bulletin_board_service,
        "admin_list_notices",
        lambda status=None, include_inactive=True, page=1, page_size=10: {
            "items": [],
            "total": 0,
            "total_pages": 1,
            "page": page,
            "page_size": page_size,
        },
    )

    result = NoticeCommand().execute(_ctx_admin(), ["list", "all", "2"])

    assert result.success
    assert "notices page 2/1 (total=0)" in result.message
    assert "No notices." in result.message


def test_notice_command_view_success(monkeypatch):
    from app.commands.admin.notice_command import NoticeCommand
    from app.commands.admin import notice_command as mod
    from unittest.mock import MagicMock

    monkeypatch.setattr(
        mod.bulletin_board_service,
        "get_notice_by_id",
        lambda notice_id, public_only=False: {
            "id": 1,
            "title": "Test Notice",
            "content_md": "**Bold** and `code`",
            "status": "published",
            "author_id": 99,
            "created_at": "2026-05-15T10:00:00",
        },
    )
    monkeypatch.setattr(
        mod.bulletin_board_service,
        "render_notice_md_to_terminal",
        lambda content_md: "Bold and code",
    )
    monkeypatch.setattr(
        mod.bulletin_board_service,
        "split_terminal_chunks",
        lambda text, max_chars=1200: [text],
    )

    # Mock user node lookup for author name resolution
    mock_user_node = MagicMock()
    mock_user_node.name = "admin"

    ctx = _ctx_admin()
    ctx.db_session.query.return_value.filter.return_value.first.return_value = mock_user_node

    cmd = NoticeCommand()
    result = cmd.execute(ctx, ["view", "1"])
    assert result.success
    assert "Test Notice" in result.message
    assert "admin" in result.message
    assert "#1 [published] Test Notice" in result.message


def test_notice_command_view_not_found(monkeypatch):
    from app.commands.admin.notice_command import NoticeCommand
    from app.commands.admin import notice_command as mod

    monkeypatch.setattr(
        mod.bulletin_board_service,
        "get_notice_by_id",
        lambda notice_id, public_only=False: None,
    )

    cmd = NoticeCommand()
    result = cmd.execute(_ctx_admin(), ["view", "999"])
    assert not result.success
    assert "999" in result.message


def test_notice_command_view_invalid_id(monkeypatch):
    from app.commands.admin.notice_command import NoticeCommand

    cmd = NoticeCommand()
    result = cmd.execute(_ctx_admin(), ["view", "abc"])
    assert not result.success
    assert "无效公告 ID" in result.message


def test_notice_command_view_missing_id(monkeypatch):
    from app.commands.admin.notice_command import NoticeCommand

    cmd = NoticeCommand()
    result = cmd.execute(_ctx_admin(), ["view"])
    assert not result.success
    assert "用法" in result.message
