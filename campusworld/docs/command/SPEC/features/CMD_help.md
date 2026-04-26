# `help`

> **Architecture Role**: 系统帮助（SYSTEM）；列出可执行命令、按名展开详细帮助，文案走 i18n 与 `resolve_locale`（`locale_text`）。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `help` |
| `CommandType` | SYSTEM |
| File | [`backend/app/commands/system_commands.py`](../../../../backend/app/commands/system_commands.py) `HelpCommand` |
| Locale | `commands.help` + `help_shell_for_locale` 字符串（`app/commands/i18n/locale_text.py`） |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |

**Aliases**: `h`, `?`（来自 `__init__`）。

## Synopsis

```
help
help <command_name>
```

- 无参：列出当前调用者可执行的命令清单（`get_available_commands(context)`）+ 一行简介（来自 `commands.<name>.description` i18n）。
- 有参：仅取首参作为命令名解析；命中则返回 `cmd.get_detailed_help_for_locale(loc)`，未命中按 `help_shell_for_locale.err_not_found` 模板报错。

## Implementation contract

- 有 1+ 个参数时：用 `get_command` 解第一参，找到则 `success_result(cmd.get_detailed_help_for_locale(loc))`；未找到用 shell `err_not_found` 模板。
- 无参时：`get_available_commands(context)` 列清单 + `get_localized_description` + 固定 footer。纯文本、无 `data` 主路径。
