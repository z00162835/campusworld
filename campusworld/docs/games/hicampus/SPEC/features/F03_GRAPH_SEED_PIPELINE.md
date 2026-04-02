# F03 - Graph Seed Pipeline

## Goal

将 F02 产出的 `PackageSnapshotV2`（空间 + 实体事实层）**幂等**实例化为图数据库中的 `nodes` 与 `relationships`，并与 `node_types` / `relationship_types` 本体对齐（Evennia 风格：可区分类型 + 可重复执行的批量装配）。

## Scope

- 快照 → 节点规格（`type_code` 经 `WorldGraphProfile` 映射到 DB `type_code`）
- 关系创建（profile 白名单子集）；`connects_to` 单向声明时自动补反向边
- 幂等 upsert（按确定性 UUID 与 `package_node_id`）
- 与 F01 可选集成：`manifest.graph_seed` / `features.graph_seed.enabled`

## Multi-World Subgraph Model（多世界子图谱）

- **语义**：多个世界包共用同一套全局图存储；每个安装的世界在图中形成 **子图谱**，由节点与边上的 `attributes.world_id` 标识边界。
- **默认隔离**：快照实例化仅在单一 `world_id` 内进行；若关系的两端解析到 **不同** `world_id`，种子流程 **拒绝写入**（异常 `GRAPH_SEED_REFERENCE_BROKEN`，提示需通过管理命令创建跨世界桥接，见 F04 `world bridge`）。
- **与 F06 对齐**：运行态若已存在未授权跨世界 `relationships`（无桥接元数据），由拓扑校验报 `UNAUTHORIZED_CROSS_WORLD_RELATIONSHIP`。

## Out of Scope

- 命令层入口与权限
- 文案模板维护流程
- **ConceptModel** 节点落库（goals/rules/skills 等）——当前**不**为概念行创建 `Node`；概念数据仅随 snapshot 供上层服务使用；若未来落库需新增 `node_types` 行与 profile 映射（见下文「概念层策略」）。

## Inputs

- **必选**：`PackageSnapshotV2`（或等价 dict：`world` / `spatial` / `entities` / `relationships` / `meta`）
- **必选**：`WorldGraphProfile`（世界包提供，如 `get_graph_profile()` → `HICAMPUS_GRAPH_PROFILE`）
- **前置**：PostgreSQL + 已执行 `ensure_graph_seed_ontology`（或等价 `node_types` / `relationship_types` 行）

## Dependencies

- 前置：`F01` `F02`
- 被依赖：`F04` `F05` `F06`

## WorldGraphProfile 契约

| 成员 | 含义 |
|------|------|
| `world_package_id` | 须与 `run_graph_seed(..., world_id=...)` 一致 |
| `map_node_type(package_type_code)` | F02 `type_code` → `node_types.type_code`；未知则 `GraphSeedError(GRAPH_SEED_TYPE_UNKNOWN)` |
| `allowed_relationship_type_codes` | 允许写入图的 `rel_type_code` 集合 |
| `strict_relationships` | 默认 `False`；为 `True` 时，snapshot 中出现不在上表中的 `rel_type_code` 则失败 |

类型登记表：`F02_ENTITY_TYPE_REGISTRY.md`。

## F01 集成（manifest）

| 键 | 说明 |
|----|------|
| `graph_seed: true` | 在 `load_game` / `reload_game` 成功路径、于注册游戏实例**之前**执行种子（需 PostgreSQL） |
| `features.graph_seed.enabled: true` | 与上一行等价（二选一） |
| `features.graph_seed.strict_relationships: true` | 未在 profile 白名单中的关系 → `GRAPH_SEED_RELATIONSHIP_UNSUPPORTED` |

世界包须导出 **`get_graph_profile(manifest=None)`**（manifest 预留扩展）。`GameLoader` 持久化 `details` 时会剥离不可 JSON 序列化的 `snapshot` 对象。

## 错误码（F03）

与 `WorldErrorCode` 一致，供 `GraphSeedError` 与 F01 结果共用：

| 码 | 场景 |
|----|------|
| `GRAPH_SEED_REFERENCE_BROKEN` | `world.id` 缺失、world_id 与 profile 不一致、关系端点未加载、**快照内关系跨 world_id（须用 F04 `world bridge`）** 等 |
| `GRAPH_SEED_TYPE_UNKNOWN` | 包 `type_code` 无映射，或 DB 缺 `node_types` / `relationship_types` 行 |
| `GRAPH_SEED_RELATIONSHIP_UNSUPPORTED` | strict 模式下出现未在白名单的关系类型 |
| `GRAPH_SEED_FAILED` | 非 PG 环境、无 snapshot、无 `get_graph_profile`、或其它未分类异常（loader 侧） |

## `run_graph_seed` 返回 `details`（观测）

| 字段 | 含义 |
|------|------|
| `nodes_upserted` / `nodes_skipped` | 新建 vs 已存在跳过 |
| `relationships_created` / `relationships_skipped` | 新建 vs 已存在跳过 |
| `relationships_ignored_count` | 因不在 profile 白名单而**未处理**的关系条数 |
| `relationships_ignored_by_type` | 按 `rel_type_code` 分桶计数 |
| `relationships_ignored_sample` | 最多 10 条示例 `{id, rel_type_code}` |
| `strict_relationships` | 本次是否严格模式 |
| `duration_ms` | 耗时 |

## 概念层策略（F02 ConceptModel）

- **当前实现**：`_build_specs` 仅为 `world`、spatial、**entities**（zones/npcs/items）建节点；**不为** `concepts/*` 创建图节点。
- **理由**：概念层多用于治理与推理绑定，与空间孪生解耦；避免与现有 `node_types` 爆炸式增长同步困难。
- **演进**：若需「概念即节点」，应新增本体行（如 `concept_goal`）、typeclass、`graph_profile` 映射，并单独 PR 扩展 `_build_specs`。

## DoD

- 重复执行不生成重复核心节点（同一 `package_node_id` + world）
- F1~F6 楼层/房间按 F02 配置落库（在启用 `graph_seed` 且 PG 可用时）
- 双向可达：`connects_to` 仅声明单向时自动补反向
- 默认模式下忽略的关系可观测（`relationships_ignored_*`）；strict 模式下非法关系失败可诊断

## 参考

- 架构修复计划：`docs/architecture/F01_F03_GAP_REMEDIATION_PLAN.md`
- Evennia：[Typeclasses](https://www.evennia.com/docs/latest/Components/Typeclasses.html)、[Objects](https://www.evennia.com/docs/latest/Components/Objects.html)
