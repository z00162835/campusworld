# `whoami`

> **Architecture Role**: 只读身份提示（SYSTEM）；从 `CommandContext.username` 返回当前主名（非「在线 who」列表）。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `whoami` |
| `CommandType` | SYSTEM |
| File | [`backend/app/commands/system_commands.py`](../../../../backend/app/commands/system_commands.py) `WhoamiCommand` |
| Locale | `commands.whoami`（不含 `who` 别名；`who` 为独立命令，见 [CMD_who.md](CMD_who.md)） |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |

**Aliases**: 空（`__init__(... [])`）；`who` **不是** 别名。

## Synopsis

```
whoami
```

- 无参；任何 args 均被忽略。
- 仅返回当前调用者主名；要看其他在线会话请使用 [`CMD_who`](CMD_who.md)。

## Implementation contract

- 单行 `commands.whoami.current_user`（含 `{username}` 占位），由 `context.username` 填充；缺失时回退英文字面量 `Current user: {username}`。
- 文案契约：`commands.whoami.current_user` 字符串必须含 `{username}`。
- 多语言路径：`resolve_locale(context)` → 命令 i18n bundle → `commands.whoami.current_user`。
- 无 `data` 主路径。
