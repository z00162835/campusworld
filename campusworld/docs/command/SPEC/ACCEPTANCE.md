# 命令系统验收检查表

## Per-command SPEC 与实现 1:1（`docs/command/SPEC/features/CMD_*.md`）

初始化或更新某命令的 SPEC 时，**实现契约占唯一真源**；下列项用于人工或 PR 审阅。生成器/快照见 [`_generated/README.md`](_generated/README.md)。

- [ ] **元数据完整**：`Implementation contract` 顶栏含锚定 **git commit**、**实现文件路径**、**校验日期**、若经脚本则 **脚本路径与版本/快照时间**（与 [`registry_snapshot.json`](_generated/registry_snapshot.json) 一致或可解释差异）。
- [ ] **可溯源**：对错误文案、`CommandResult.data` 键名、互斥条件等，注明 **源码位置** 或 **测试用例**（`backend/tests/...`）以便复查。
- [ ] **不混入未实现行为**：`Implementation contract` 中不出现代码未分支的断言；产品设想放在 **Non-Goals / Roadmap**，且不与契约矛盾。
- [ ] **与注册表一致**：命令主名、别名、类型与 `initialize_commands()` 后注册表一致；变更命令行为时 **同 PR** 更新对应 `CMD_*.md` 或重跑 `backend/scripts/export_command_registry_snapshot.py`。
- [ ] **`find` / `describe` SSOT**：[F01_FIND_COMMAND](features/F01_FIND_COMMAND.md) 为图检索**深文档**；`CMD_find` / `CMD_describe` 为摘要+链接，避免双份契约冲突。

## 基础功能验收

- [ ] `BaseCommand.execute()` 返回 `CommandResult`（非 None）
- [ ] `CommandRegistry.get_command("look")` 能找到 look 命令
- [ ] `CommandRegistry.get_command("l")` 能找到 look 命令（别名）
- [ ] `CommandRegistry.execute("look", context, [])` 正常执行
- [ ] 未知命令 `CommandRegistry.execute("foo", ...)` 返回错误

## 权限验收

- [ ] SYSTEM 命令对所有用户开放
- [ ] GAME 命令需要对应 `game.[name]` 权限
- [ ] ADMIN 命令需要 `admin` 权限
- [ ] 权限不足时返回 `CommandResult.success=False`

## 状态机验收

```
输入 "look"
    ↓ 解析
找到 LookCommand
    ↓ 检查权限
通过
    ↓ 执行
返回房间描述
    ↓ 验证
CommandResult.success == True
```

## SSH 集成验收

- [ ] SSH 终端输入 `look` 返回房间描述
- [ ] SSH 终端输入 `help` 返回命令列表
- [ ] SSH 终端输入 `who` 返回在线用户

## 性能验收

- [ ] 命令解析 + 执行总耗时 < 50ms
- [ ] 命令注册表初始化 < 100ms