# HiCampus Features Index

> 本目录用于团队并行开发，每个特性文档定义独立边界、依赖与验收标准。

## Feature List

- `F01` World Package Runtime  
  `F01_WORLD_PACKAGE_RUNTIME.md`
- `F02` World Data Package  
  `F02_WORLD_DATA_PACKAGE.md`
- `F03` Graph Seed Pipeline  
  `F03_GRAPH_SEED_PIPELINE.md`
- `F04` World Management Commands  
  `F04_WORLD_MANAGEMENT_COMMANDS.md`
- `F05` World Entry Integration  
  `F05_WORLD_ENTRY_INTEGRATION.md`
- `F06` Topology Validate & Repair  
  `F06_TOPOLOGY_VALIDATE_REPAIR.md`
- `F07` Spatial Narrative & Description Content Pack  
  `F07_SPATIAL_DESCRIPTION_CONTENT_PACK.md`
- `F08` Observability & Audit  
  `F08_OBSERVABILITY_AUDIT.md`

## Suggested Parallel Lanes

- **Lane A（核心运行）**: `F01 + F02 + F03`
- **Lane B（系统集成）**: `F05 + F04`
- **Lane C（质量保障）**: `F06 + F08`
- **Lane D（内容资产）**: `F07`

## Merge Gate

1. `F01/F02` 通过后，允许 `F03` 合并主线。
2. `F03` 完成后，`F05` 可做端到端联调。
3. `F04` 可在 `F01` 稳定后并行开发，联调依赖 `F03/F06`。
4. `F07` 独立并行，可在任一阶段补充，不阻塞核心链路。
