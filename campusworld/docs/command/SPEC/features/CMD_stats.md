# `stats`

> **Architecture Role**: 只读系统/进程类信息（SYSTEM）；`StatsCommand` 汇总运行态统计（以实码输出为准）。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `stats` |
| `CommandType` | SYSTEM |
| File | [`backend/app/commands/system_commands.py`](../../../../backend/app/commands/system_commands.py) `StatsCommand` |
| Locale | `commands.stats`（含 `stats.title` / `stats.error` 文案 key） |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |

**Aliases**: `stat`, `system`（来自 `__init__`）。

## Synopsis

```
stats
```

- 无参；任何 args 均被忽略。
- 别名 `stat` / `system` 同义。

## Implementation contract

- 使用 `psutil` 采集 CPU/内存/磁盘/平台/Python，格式化为多行块输出；标题来自 `commands.stats.title`（默认 `System Statistics`）。
- 文案契约：`commands.stats.title` 为标题字符串；`commands.stats.error` 为格式串（含 `{error}` 占位），用于异常路径 `error_result(...)`。
- 多语言路径：`resolve_locale(context)` → 命令 i18n bundle → `commands.stats.{title,error}`。
- 数值字段格式（`CPU Usage`、`Memory`、`Disk`、`Platform`、`Python`、`Uptime`）保持英文键名以便机器/agent 解析。
