# F04 - World Management Commands

## Goal

实现系统命令族 `world`，提供安装、卸载、重载、校验、修复、状态查询能力。

## Scope

- 命令语法与解析
- 权限校验（`admin.world.*`）
- 输出契约与错误码
- 审计日志写入

## Command Set

- `world list`
- `world install <world_id>`
- `world uninstall <world_id>`
- `world reload <world_id>`
- `world status <world_id>`
- `world validate <world_id>`
- `world repair <world_id>`

## Dependencies

- 前置：`F01`
- 联调依赖：`F03` `F06`

## DoD

- 命令输出符合 SPEC 契约
- `--dry-run`、`--force` 行为正确
- 错误码与提示可用于运维定位
