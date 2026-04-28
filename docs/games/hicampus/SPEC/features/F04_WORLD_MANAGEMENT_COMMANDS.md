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

### Cross-World Bridge（跨世界连接，默认不联通）

仅管理员通过子命令显式建立；默认任意两世界 **不** 在图上直连。

| 子命令 | 权限 | 说明 |
|--------|------|------|
| `world bridge add <src_world> <src_room_pkg> <direction> <dst_world> <dst_room_pkg>` | `admin.world.bridge.manage` | 创建 `connects_to` + `cross_world_bridge` 元数据；可选 `--two-way`、`--bridge-type`（portal / gate / transit）、`--dry-run` |
| `world bridge remove <bridge_id>` 或 `remove <src_world> <src_room_pkg> <direction>` | `admin.world.bridge.manage` | 停用桥接关联边 |
| `world bridge list [<world_id>] [--include-disabled]` | `admin.world.bridge.read` | 列出桥接；可按世界过滤 |
| `world bridge validate <world_id>` | `admin.world.bridge.read` | 仅针对 **未授权跨世界关系** 的报告（`UNAUTHORIZED_CROSS_WORLD_RELATIONSHIP`） |

**错误码（节选）**：`WORLD_BRIDGE_PERMISSION_DENIED`、`WORLD_BRIDGE_INVALID_ARGUMENT`、`WORLD_BRIDGE_NOT_FOUND`、`WORLD_BRIDGE_ALREADY_EXISTS`、`WORLD_BRIDGE_CROSS_BOUNDARY_VIOLATION`、`WORLD_BRIDGE_DIRECTION_CONFLICT`、`WORLD_BRIDGE_APPLY_FAILED`。

**审计事件**：`world.bridge.add.attempt|success|fail`、`world.bridge.remove.attempt|success|fail`、`world.bridge.list`、`world.bridge.validate`。

**与移动**：本世界同方向存在本地 `connects_to` 时 **优先本地**；无本地出口时才尝试启用中的跨世界桥接；桥接关闭时 `WORLD_BRIDGE_DISABLED`。

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

- 权限：`admin.world.*`（可细分为 `admin.world.read/manage/maintain`）；跨世界桥接另需 `admin.world.bridge.read` / `admin.world.bridge.manage`（可由 `admin.world.*` 通配覆盖）。
- 鉴权失败：返回 `WORLD_FORBIDDEN`（既有子命令）或 `WORLD_BRIDGE_PERMISSION_DENIED`（`world bridge`）。
- **分层**：`WORLD_BOUNDARY_*` / `WORLD_TOPOLOGY_*`（拓扑）、`WORLD_BRIDGE_*`（桥接命令与服务）、`GRAPH_SEED_*`（F03 种子）。
- `world bridge validate` 在未授权跨世界问题时：`success=false`，`error=WORLD_BOUNDARY_VIOLATION`。
- 运行时/数据/种子失败：沿用 `WORLD_*`、`WORLD_DATA_*`、`GRAPH_SEED_*` 错误码。

## Dependencies

- 前置：`F01`
- 联调依赖：`F03` `F06`

## DoD

- 命令输出符合 SPEC 契约
- `--dry-run`、`--force` 行为正确
- 错误码与提示可用于运维定位
