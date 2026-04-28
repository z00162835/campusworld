# `create`

> **Architecture Role**: 通用对象建造（ADMIN）；以 `ModelDiscoverer` 发现的领域模型为目标，`create ClassName = {…}` 直接装配并持久化。**全局注册**而非单 agent 能力，建模时与 [`CMD_create_info`](CMD_create_info.md) 配合：`create_info` 查模型字段，`create` 实际写入。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `create` |
| `CommandType` | ADMIN |
| Class | `app.commands.builder.create_command.CreateCommand` |
| Primary implementation | [`backend/app/commands/builder/create_command.py`](../../../../backend/app/commands/builder/create_command.py) |
| Locale | `commands.create` |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |

**Aliases**（`registry_aliases`）: 见快照（`spawn`/`build`/`make` 等，以 `class_declared`+注册为准）。

## Synopsis

```
create <ClassName> = {<dict literal | JSON>}
```

- 来源：`get_usage()` → `create ClassName = {参数}`。
- 整串必须含 `=`，且 `len(args) >= 2`（见 `validate_args`）。
- 参数体优先 `ast.literal_eval`，失败后退到 `json.loads`；必须可解析为 `dict`。

## Implementation contract

- `validate_args`：整串须含 `=` 且 `len >= 2` 词法（见 `validate_args` 与 `execute` 内联解析）。
- `execute`：`_parse_create_command` 失败时返回其 `error` 字符串；成功时走 `ModelDiscoverer`（以文件内同名为准）/模型实例化/持久化；异常路径见源码 `error_result(...)` 中文/英文信息。

> 实现内引用 `ModelDiscoverer` 的静态用法与 `model_discoverer` 需与 [`create_command.py`](../../../../backend/app/commands/builder/create_command.py) 一致；不在这里照抄行号，以免漂移。

## Tests

- 建造与模型发现相关测试在 `backend/tests`（若有 grep `CreateCommand` / `create `）。
