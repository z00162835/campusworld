# F06 - Topology Validate & Repair

## Goal

提供 `HiCampus` 拓扑与核心节点一致性的自动校验与修复能力。

## Scope

- strict 校验规则（核心节点、双向边、楼层数量）
- 修复计划生成（dry-run）
- 自动修复执行与报告

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
