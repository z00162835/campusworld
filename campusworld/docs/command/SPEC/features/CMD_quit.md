# `quit`

> **Architecture Role**: 会话生命周期（SYSTEM）；请求结束当前 SSH/交互会话（具体断连由协议层处理，见实码）。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `quit` |
| `CommandType` | SYSTEM |
| File | [`backend/app/commands/system_commands.py`](../../../../backend/app/commands/system_commands.py) `QuitCommand` |
| Locale | `commands.quit`（含 `quit.goodbye` 文案 key） |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |

**Aliases**: `exit`, `q`（来自 `__init__`，以注册快照为准）。

## Synopsis

```
quit
```

- 无参；任何 args 均被忽略（不报错）。
- 别名 `exit` / `q` 同义。

## Implementation contract

- `CommandResult.success_result(<commands.quit.goodbye>)` 且 `result.should_exit = True`（由 SSH/协议消费）。
- 文案契约：成功消息字符串为 `commands.quit.goodbye`；缺失时回退英文字面量 `Goodbye!`。
- 多语言路径：`resolve_locale(context)` → 命令 i18n bundle → `commands.quit.goodbye`。
