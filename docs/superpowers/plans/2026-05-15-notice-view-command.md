# `notice view` 子命令实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `notice` 命令添加 `view` 子命令，支持查看单条公告的完整内容（标题 + 正文），遵循项目 i18n 规范。

**Architecture:** 在 `NoticeCommand` 中新增 `_view` 方法，通过 `bulletin_board_service.get_notice_by_id()` 获取公告数据，使用 `render_notice_md_to_terminal()` 渲染正文，复用 `who` 命令的 i18n 模式（`get_command_i18n_text`）。

**Tech Stack:** Python, BulletinBoardService, i18n YAML

---

## File Structure

```
backend/
├── app/commands/admin/notice_command.py      # 修改：添加 _view 方法
├── app/commands/i18n/locales/zh-CN.yaml     # 修改：添加 notice.view.* i18n
├── app/commands/i18n/locales/en-US.yaml     # 修改：添加 notice.view.* i18n
├── tests/commands/test_notice_command.py     # 修改：添加 view 测试用例
docs/command/SPEC/features/CMD_notice.md      # 修改：更新 SPEC
```

---

## Task 1: 添加 `_view` 方法到 NoticeCommand

**Files:**
- Modify: `backend/app/commands/admin/notice_command.py:10-44`

- [ ] **Step 1: 添加 view 分支到 execute 方法**

在 `execute` 方法的 action dispatch 中添加 `view` 分支，更新 `__init__` 描述和错误提示。

修改位置约在 line 14 和 line 18-28：

```python
def __init__(self):
    super().__init__(name='notice', description='管理系统公告(publish/edit/archive/list/view)', aliases=['notices'])
```

```python
def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
    if not args:
        return CommandResult.error_result('用法: notice <publish|edit|archive|list|view> ...')
    # ... action dispatch ...
    if action == 'view':
        return self._view(context, rest)
```

- [ ] **Step 2: 实现 `_view` 方法**

在 `_list` 方法之后添加 `_view` 方法（line 95 之后）：

```python
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
    author = dto.get('author_name') or dto.get('author_id') or 'unknown'
    created_at = dto.get('created_at', '')

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
```

- [ ] **Step 3: 运行测试验证**

```bash
cd backend
conda run -n campusworld pytest tests/commands/test_notice_command.py -v
```

预期：现有测试通过（暂未添加 view 测试，下一步添加）

---

## Task 2: 添加 i18n 国际化文本

**Files:**
- Modify: `backend/app/commands/i18n/locales/zh-CN.yaml:78-79`
- Modify: `backend/app/commands/i18n/locales/en-US.yaml:78-79`

- [ ] **Step 1: 更新中文 i18n（zh-CN.yaml）**

在 `notice` 条目下添加 `view` 相关文本（约 line 78-79）：

```yaml
  notice:
    description: "管理系统公告(publish/edit/archive/list/view)"
    view:
      header: "公告详情"
      author: "作者"
      time: "时间"
      error:
        usage: "用法: notice view <id>"
        invalid_id: "无效公告 ID"
        not_found: "公告不存在: #{id}"
```

- [ ] **Step 2: 更新英文 i18n（en-US.yaml）**

```yaml
  notice:
    description: "Manage system bulletins (publish/edit/archive/list/view)"
    view:
      header: "Notice Detail"
      author: "Author"
      time: "Time"
      error:
        usage: "Usage: notice view <id>"
        invalid_id: "Invalid notice ID"
        not_found: "Notice not found: #{id}"
```

- [ ] **Step 3: 验证 i18n 加载**

```bash
cd backend
conda run -n campusworld python -c "
from app.commands.i18n.command_resource import get_command_i18n_text
print(get_command_i18n_text('notice', 'view.header', 'zh-CN', 'default'))
print(get_command_i18n_text('notice', 'view.header', 'en-US', 'default'))
"
```

预期：
```
公告详情
Notice Detail
```

---

## Task 3: 添加单元测试

**Files:**
- Modify: `backend/tests/commands/test_notice_command.py:85-119`

- [ ] **Step 1: 添加 view 成功测试**

在 `test_notice_command_edit_archive_and_list` 之后添加（约 line 119）：

```python
def test_notice_command_view_success(monkeypatch):
    from app.commands.admin.notice_command import NoticeCommand
    from app.commands.admin import notice_command as mod

    monkeypatch.setattr(
        mod.bulletin_board_service,
        "get_notice_by_id",
        lambda notice_id, public_only=False: {
            "id": 1,
            "title": "Test Notice",
            "content_md": "**Bold** and `code`",
            "status": "published",
            "author_name": "admin",
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

    cmd = NoticeCommand()
    result = cmd.execute(_ctx_admin(), ["view", "1"])
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
```

- [ ] **Step 2: 运行新测试**

```bash
cd backend
conda run -n campusworld pytest tests/commands/test_notice_command.py::test_notice_command_view_success -v
conda run -n campusworld pytest tests/commands/test_notice_command.py::test_notice_command_view_not_found -v
conda run -n campusworld pytest tests/commands/test_notice_command.py::test_notice_command_view_invalid_id -v
conda run -n campusworld pytest tests/commands/test_notice_command.py::test_notice_command_view_missing_id -v
```

预期：全部 PASS

- [ ] **Step 3: 运行完整 notice 测试套件**

```bash
cd backend
conda run -n campusworld pytest tests/commands/test_notice_command.py -v
```

预期：全部测试通过（包括原有的 publish/edit/archive/list 测试）

---

## Task 4: 更新 SPEC 文档

**Files:**
- Modify: `docs/command/SPEC/features/CMD_notice.md`

- [ ] **Step 1: 更新 CMD_notice.md**

将 `notice` 的 SPEC 从：

```markdown
## Synopsis

```
notice publish <title> | <content_md>
notice edit <id> <title> | <content_md>
notice archive <id>
notice list [all|published|draft|archived] [page]
```
```

更新为：

```markdown
## Synopsis

```
notice publish <title> | <content_md>
notice edit <id> <title> | <content_md>
notice archive <id>
notice list [all|published|draft|archived] [page]
notice view <id>
```
```

并在 `list` 说明后添加 `view` 说明：

```markdown
- `view`：`notice view <id>`；读取单条公告完整内容（标题、作者、时间、正文）；正文经 `render_notice_md_to_terminal` 渲染为终端安全文本，超长内容自动分块。
```

- [ ] **Step 2: 更新 i18n status**

将 i18n status 部分更新：

```markdown
## i18n status

- `notice.view.header`、`notice.view.author`、`notice.view.time` 提供 view 输出标题行 i18n。
- `notice.view.error.usage`、`notice.view.error.invalid_id`、`notice.view.error.not_found` 提供 view 错误文案 i18n。
- 原有 `publish/edit/archive/list` 错误中文硬编码问题已锚定（见上期 TODO），本期不动。
```

---

## Task 5: 提交变更

- [ ] **Step 1: 验证所有测试通过**

```bash
cd backend
conda run -n campusworld pytest tests/commands/test_notice_command.py -v
```

- [ ] **Step 2: 提交**

```bash
cd /Users/xbit/code/campusworld
git add backend/app/commands/admin/notice_command.py \
      backend/app/commands/i18n/locales/zh-CN.yaml \
      backend/app/commands/i18n/locales/en-US.yaml \
      backend/tests/commands/test_notice_command.py \
      docs/command/SPEC/features/CMD_notice.md
git commit -m "feat(command): add notice view subcommand

- Add notice view <id> to display full notice content
- Use bulletin_board_service.get_notice_by_id() + render_notice_md_to_terminal()
- Add i18n keys for view header and error messages
- Add unit tests for view success/not_found/invalid_id/missing_id"
```

---

## Self-Review Checklist

- [ ] `view` 分支已添加到 `execute()` dispatch
- [ ] `_view` 方法使用 `get_command_i18n_text` i18n 模式（与 `who`/`stats` 一致）
- [ ] `bulletin_board_service.get_notice_by_id()` 调用成功返回公告数据
- [ ] `render_notice_md_to_terminal()` 用于渲染 markdown 正文
- [ ] `split_terminal_chunks()` 用于处理超长公告
- [ ] zh-CN.yaml 和 en-US.yaml 都已更新
- [ ] 4 个测试用例覆盖 success/not_found/invalid_id/missing_id
- [ ] CMD_notice.md SPEC 已更新
- [ ] 所有测试通过后再提交
