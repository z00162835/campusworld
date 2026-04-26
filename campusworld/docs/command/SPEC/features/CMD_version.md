# `version`

> **Architecture Role**: 只读系统信息（SYSTEM）；输出版本/构建信息类字符串（见 `VersionCommand` 实码）。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `version` |
| `CommandType` | SYSTEM |
| File | [`backend/app/commands/system_commands.py`](../../../../backend/app/commands/system_commands.py) `VersionCommand` |
| Locale | `commands.version` |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |

**Aliases**: `ver`（来自 `__init__`）。

## Synopsis

```
version
```

- 无参；任何 args 均被忽略。
- 别名 `ver` 同义。

## Implementation contract

- 固定返回含 `CampusWorld System` / `Version: 0.1.0` / `Environment: development` 等行块的文本（多行英文模板，未走 i18n）。
- 无参数、无 `data` 载荷；后续若引入 i18n 应以 `commands.version.template` 类似 key 接入，本期暂不变。
