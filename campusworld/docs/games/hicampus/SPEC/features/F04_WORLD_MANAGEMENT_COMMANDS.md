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
- `world validate <world_id> [--dry-run]`
- `world repair <world_id> [--dry-run] [--force]`

## Runtime Output Contract

`world install/uninstall/reload` 的输出应透传运行时结构化结果（见 F01）并在命令层附加路径观测字段：

```json
{
  "ok": true,
  "world_id": "hicampus",
  "job_id": "uuid",
  "status_before": "not_installed",
  "status_after": "installed",
  "error_code": null,
  "message": "world loaded",
  "details": {},
  "resolved_path": "/abs/path/to/world",
  "source_type": "builtin|external|custom"
}
```

`world list` 输出：

```json
{
  "items": [
    {
      "world_id": "hicampus",
      "loaded": true,
      "resolved_path": "/abs/path/to/world",
      "source_type": "builtin"
    }
  ],
  "total": 1
}
```

`world status` 输出至少包含：
- `world_id`
- `game_info`
- `runtime_state`
- `resolved_path`
- `source_type`

`world validate/repair` 输出至少包含：
- `world_id`
- `dry_run`
- `report`（issues/planned_actions/applied_actions/skipped_actions/ok）

## Flag Semantics

- `world validate <world_id> --dry-run`：仅输出校验报告（默认不写库）。
- `world repair <world_id> --dry-run`：仅输出修复动作计划，不执行。
- `world repair <world_id> --force`：允许执行风险修复动作（当前实现中，补反向 `connects_to` 边需要 `force=true`）。
- 同时传 `--dry-run --force` 时，`dry-run` 优先，`force` 不触发写操作。

## Error / Permission Contract

- 权限：`admin.world.*`（可细分为 `admin.world.read/manage/maintain`）。
- 鉴权失败：返回 `WORLD_FORBIDDEN`。
- 运行时/数据/种子失败：沿用 `WORLD_*`、`WORLD_DATA_*`、`GRAPH_SEED_*` 错误码。

## Dependencies

- 前置：`F01`
- 联调依赖：`F03` `F06`

## DoD

- 命令输出符合 SPEC 契约
- `--dry-run`、`--force` 行为正确
- 错误码与提示可用于运维定位
