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

## Repair Actions (v1)

- `create_reverse_connects_to`
  - 触发条件：`CONNECTS_TO_REVERSE_MISSING`
  - `dry-run`: 仅计划，不写库
  - 执行条件：`force=true`
  - 执行结果：记录到 `applied_actions` 或 `skipped_actions`

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
- 文案资产维护（见 `F07`）

## Dependencies

- 前置：`F03`
- 被依赖：`F04`（world validate/repair）

## DoD

- 能识别：缺失节点、错向边、楼层不一致
- dry-run 输出可执行动作清单
- 修复后再次校验通过
