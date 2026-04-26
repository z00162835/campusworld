# `CMD_<name>`

> Copy to `../features/CMD_<name>.md` and fill placeholders. **Implementation contract** 必须与当前代码一致；叙述性/规划内容放 **旁注** 或 **Non-Goals / Roadmap**。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `<name>` |
| Aliases | (from class / registry; run `export_command_registry_snapshot.py`) |
| `CommandType` | SYSTEM \| GAME \| ADMIN |
| Primary implementation | `backend/.../....py` |
| Locale keys | `backend/app/commands/i18n/locales/{zh-CN,en-US}.yaml` → `commands.<name>.*` |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) (`git_commit`) |
| Last reviewed | YYYY-MM-DD |

## Synopsis

- **Usage** (与 `get_usage()` / 解析器一致，若无覆盖则自 `execute` 与 docstring 归纳):

```
<copy from code>
```

## Implementation contract (SSOT: code)

- **主路径 / 错误形态**: 简述 `execute()` 分支；列出用户可见错误字符串及 `CommandResult` / `data` 键名（可注明源码行或测试用例名）。
- **权限 / 策略**: `command_policies` 或 `AdminCommand` / 子命令检查（如适用）。
- **副作用**: 只读 | 图写 | 提交 session | 等。
- **i18n**: 列表类帮助来自 `locales`；硬编码字符串在契约中逐字记录。

## Non-Goals / Roadmap (optional)

产品设想或未实现项；**不得**与 **Implementation contract** 矛盾。

## 相关

- 总表: [../SPEC.md](../SPEC.md)
- 图检索深文档: 仅 `find` / `describe` 见 [F01_FIND_COMMAND.md](../features/F01_FIND_COMMAND.md)（`CMD_find` / `CMD_describe` 为摘要，不重复 F01 契约）

## Tests

- `backend/tests/...`（有则列；无则写 `N/A` 并说明依赖手工/集成路径）

---

### 轻量/重量两档

- **轻量**（`time` / 方向子命令等）：Metadata + 短 **Implementation contract** + Tests 一行即可。
- **重量**（`look` / `world` / F01 类）：在契约下增加子节、边界表、Mermaid 流程；仍避免与代码不一致的断言。
