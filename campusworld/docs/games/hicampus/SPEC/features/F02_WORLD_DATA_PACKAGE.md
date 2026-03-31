# F02 - World Data Package

## Goal

定义 `HiCampus` 独立数据目录与数据文件规范，确保与全局 `seed_data.py` 解耦。

## Scope

- `games/hicampus/data/*` 文件组织与版本化
- world-scoped migration 规则
- 数据完整性基础校验（文件级）

## Out of Scope

- 节点写库逻辑（见 `F03`）
- 命令交互（见 `F04`）

## Data Files

- `world.yaml`
- `buildings.yaml`
- `floors.yaml`
- `rooms.yaml`
- `relationships.yaml`

## Dependencies

- 前置：无
- 被依赖：`F03` `F06`

## DoD

- `seed_minimal` 不创建 HiCampus 业务节点
- 缺失数据文件时返回明确错误码
- 数据目录可独立升级与回滚
