# F06 - Topology Validate & Repair

## Goal

提供 `HiCampus` 拓扑与核心节点一致性的自动校验与修复能力。

## Scope

- strict 校验规则（核心节点、双向边、楼层数量）
- 修复计划生成（dry-run）
- 自动修复执行与报告

## Current Rule Set (v1)

- `CORE_NODE_MISSING`：核心房间缺失（`hicampus_gate` / `hicampus_bridge` / `hicampus_plaza`）。
- `CONNECTS_TO_REVERSE_MISSING`：存在 `A -> B` 但缺失 `B -> A`。
- `FLOOR_COUNT_MISMATCH`：`building.floors_total` 与 `building_floor` 节点数不一致。
- `UNAUTHORIZED_CROSS_WORLD_RELATIONSHIP`：关系两端 `world_id` 不同，且 **未** 带授权桥接元数据（`cross_world_bridge` + `bridge_id`，见 F04）。默认跨世界不联通；仅管理员 `world bridge add` 写入的边视为合规。
- `SESSION_WORLD_LOCATION_ROOM_MISSING`：账号 `active_world` 指向当前校验世界，但 `world_location` 无法解析到活跃房间节点。
- `SESSION_ACTIVE_WORLD_LOCATION_MISMATCH`：账号 `active_world` 与 `world_location` 所指房间的 `world_id` 不一致。

## Multi-World Subgraph（术语）

- **子图谱**：同一全局图中，`world_id` 相同的节点与（同世界内的）关系集合。
- **桥接边**：`connects_to` 且 `attributes.cross_world_bridge=true` 并具有 `bridge_id`；允许端点分属两个世界。
- **边界校验**：按世界校验时，扫描「触及该世界任一节点」的关系，若跨 `world_id` 且非桥接则报上述 issue。

## Repair Actions (v1)

- `create_reverse_connects_to`
  - 触发条件：`CONNECTS_TO_REVERSE_MISSING`
  - `dry-run`: 仅计划，不写库
  - 执行条件：`force=true`
  - 执行结果：记录到 `applied_actions` 或 `skipped_actions`

- `disable_unauthorized_cross_world_link`
  - 触发条件：`UNAUTHORIZED_CROSS_WORLD_RELATIONSHIP`
  - `dry-run`：仅列入 `planned_actions`
  - 执行条件：`force=true`（与 v1 反向边一致：`--dry-run` 优先于写库）
  - 行为：将对应 `relationship` 标记为 `is_active=false`；**不**删除已授权桥接边（带 `cross_world_bridge` + `bridge_id` 的边在应用阶段会 skip）

## Validate / Repair Report Contract

`validate` 报告：

```json
{
  "world_id": "hicampus",
  "ok": false,
  "issue_count": 2,
  "issues": [{"code": "...", "message": "...", "details": {}}]
}
```

`repair` 报告：

```json
{
  "world_id": "hicampus",
  "dry_run": true,
  "force": false,
  "issues_count": 2,
  "planned_actions": [],
  "applied_actions": [],
  "skipped_actions": [],
  "ok": false
}
```

## Out of Scope

- 命令前端语法（见 `F04`）
- 空间叙事与描述资产维护（见 `F07`）

## Dependencies

- 前置：`F03`
- 被依赖：`F04`（world validate/repair）

## DoD

- 能识别：缺失节点、错向边、楼层不一致
- dry-run 输出可执行动作清单
- 修复后再次校验通过
