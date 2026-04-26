# `time`

> **Architecture Role**: 只读系统信息（SYSTEM）；返回服务器本地时间字符串，无图访问。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `time` |
| `CommandType` | SYSTEM |
| File | [`backend/app/commands/system_commands.py`](../../../../backend/app/commands/system_commands.py) `TimeCommand` |
| Locale | `commands.time`（含 `time.format` 文案 key） |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |

**Aliases**: `date`（来自 `__init__`）。

## Synopsis

```
time
```

- 无参；任何 args 均被忽略。
- 别名 `date` 同义。

## Implementation contract

- `current_time = time.strftime('%Y-%m-%d %H:%M:%S')`，格式串来自 `commands.time.format`（含 `{time}` 占位）。
- 文案契约：`commands.time.format` 必须包含一次 `{time}`；缺失时回退英文字面量 `Current time: {time}`。
- 输出为单行成功消息；无 `data` 主路径。
