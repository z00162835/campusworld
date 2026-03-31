# F03 - Graph Seed Pipeline

## Goal

将 `BuildingProfile/FloorProfile/RoomProfile` 模板实例化为图节点与关系。

## Scope

- 模板解析器
- 节点创建器（type_code 映射）
- 关系创建器（contains/connects_to/located_in）
- 幂等执行策略

## Out of Scope

- 命令层入口与权限
- 文案模板维护流程

## Inputs

- `F02` 的独立数据目录文件
- 主 SPEC 中 `type_code` 与关系建议

## Dependencies

- 前置：`F01` `F02`
- 被依赖：`F04` `F05` `F06`

## DoD

- 重复执行不生成重复核心节点
- F1~F6 楼层/房间按配置落库
- 双向可达关系完整（A->B 与 B->A）
