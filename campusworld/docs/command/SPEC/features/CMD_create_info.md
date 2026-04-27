# `create_info`

> **Architecture Role**: 模型自省辅助（ADMIN）；只读，列出可建造模型的字段元数据，与 [`CMD_create`](CMD_create.md) 互补（先 `create_info` 看字段，再 `create` 写入）。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `create_info` |
| `CommandType` | ADMIN |
| Class | `app.commands.builder.create_command.CreateInfoCommand` |
| Primary implementation | [`backend/app/commands/builder/create_command.py`](../../../../backend/app/commands/builder/create_command.py) |
| Locale | `commands.create_info` |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json)（别名 `cinfo`/`model_info`） |
| Last reviewed | 2026-04-26 |

## Synopsis

```
create_info <model_name>
```

- 来源：`get_usage()` → `create_info <模型名>`。
- 恰一个参数；若 `model_name` 不在 `ModelDiscoverer.list_models()` 中，错误文案：`未找到模型 '<name>'。可用模型: ...`。

## Implementation contract

- 恰 1 个参：`ModelDiscoverer.get_model_info(model_name)`，未找到则 `未找到模型 '…'。可用模型: ...` 错误；成功则 `message` 为 `model_info` 字符串体。
- `get_usage()` 文档串：`create_info <模型名>`（中文）。

## Tests

- 与 `create` 共用建造型测试（若有）。
