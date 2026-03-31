# F07 - MUD Description Content Pack

## Goal

将楼栋/楼层/房间描述作为独立内容资产维护，支持持续迭代与版本控制。

## Scope

- `brief/short/look/ambient` 描述模板体系
- Building/Floor/Room 分层文案模型
- 内容版本与回滚策略

## Out of Scope

- 图结构实例化（见 `F03`）
- 命令安装/校验流程（见 `F04/F06`）

## Dependencies

- 前置：无（可独立并行）
- 联动：`F03`（实例化注入字段）

## DoD

- 可批量应用模板到节点实例
- 文案升级不改变节点主键与关系结构
- 支持按版本回退内容
