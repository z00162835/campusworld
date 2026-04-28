# F07 - Spatial Narrative & Description Content Pack

## Goal

将楼栋、楼层、房间的**空间叙事与展示文案**作为独立内容资产维护，支持持续迭代与版本控制；属性键对齐园区语义模型（`Room` / `Building` / `BuildingFloor`），与图结构实例化解耦。

## Scope

- 展示层字段：`room_description` / `room_short_description` / `room_ambiance`；建筑 `building_description` / `building_tagline`；楼层 `floor_description` / `floor_short_description`。
- Building / Floor / Room 分层文案与解析继承（Room 优先，可自 Floor → Building 回退，默认不写回子节点）。
- 可选侧车目录 `content/descriptions/` 合并进快照；内容版本号与回滚策略（Git 真源 + 可选应用前快照）。
- 校验：`baseline_profile` 核心房间 P0 字段门禁；可选全量缺失报告。

## Out of Scope

- 图结构实例化（见 `F03`）
- 命令安装与拓扑校验流程（见 `F04` / `F06`）

## Dependencies

- 前置：无（可独立并行）
- 联动：`F03`（实例化将 YAML 扩展字段写入节点 `attributes`）

## DoD

- 可批量应用（图种子或 `world content apply`）到节点实例，且不改变节点主键与关系结构
- 文案升级仅更新 `attributes` 中约定键
- 支持按版本回退内容（文档化流程 + 可选快照文件）

## 运维命令（需 `admin.world.maintain`）

- `world content validate <world_id> [--report]`：全量包校验（含 P0）；`--report` 附加完备性缺口列表。
- `world content diff <world_id>`：对比包与库中同 `package_node_id` 节点的描述相关字段差异。
- `world content apply <world_id> [--dry-run] [--no-snapshot]`：将包内字段合并写入已存在节点；`--dry-run` 不提交；默认在 `data/content/revisions/` 写入应用前快照 JSON，`--no-snapshot` 可关闭。

## 回滚

1. 用 Git 恢复 `data/`（及侧车）到目标版本。  
2. 再执行 `world content apply` 或重跑图种子（仅改文案时优先 apply）。  
3. `content/revisions/*.json` 供审计与手工对照，本阶段不提供自动 revert。

## Field contract (summary)

| 概念 | 工程键（房间） | 工程键（楼层/建筑） |
|------|----------------|---------------------|
| 主叙述 | `room_description` | `floor_description`, `building_description` |
| 短描 / 一行摘要 | `room_short_description` | `floor_short_description`, `building_tagline` |
| 氛围 | `room_ambiance` | — |

建筑一行摘要固定为 **`building_tagline`**（与 `building_abbreviation` 区分）。

## Floor index

包内 YAML 可使用 `floor_no`；加载时归一为节点属性 **`floor_number`**（与 `BuildingFloor` 模型一致），并保留 `floor_no` 若需兼容。
