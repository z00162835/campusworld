# HiCampus 实体与空间类型登记表（F02 ↔ node_types ↔ Python typeclass）

> **单一事实来源**：F02 数据包中的 `type_code`、数据库 `node_types.type_code`、以及可导入的 Python typeclass（Evennia Level 3）必须与本表一致。  
> 执行计划与约束见 [TYPECLASS_ONTOLOGY_EXEC_PLAN.md](../../../../architecture/TYPECLASS_ONTOLOGY_EXEC_PLAN.md)；按 PR 拆分见 [TYPECLASS_ONTOLOGY_PR_WORK_PLAN.md](../../../../architecture/TYPECLASS_ONTOLOGY_PR_WORK_PLAN.md)。

## 命名规范

- **F02 / DB `type_code`**：小写蛇形（`access_terminal`、`building_floor`）。
- **Python 类名**：PascalCase，且在 **`app.models` 全仓库全局唯一**（C-08）。
- **`module_path` + `classname`**：须可被 `importlib` 解析；相关模块须在应用加载路径中被 **显式 import**（见 `app.models.__init__.py`），否则运行时无法发现 typeclass。

## 登记表

| f2_package_type_code | db_node_type_code | python_module_path | python_class | parent_type_code | notes |
|----------------------|-------------------|--------------------|--------------|------------------|-------|
| world | world | app.models.world | World | — | 世界根节点 |
| building | building | app.models.world | WorldObject | — | 建筑模板 |
| building_floor | building_floor | app.models.world | WorldObject | — | 楼层 |
| room | room | app.models.room | Room | — | 空间房间 |
| world_object | world_object | app.models.world | WorldObject | — | 泛化可放置物/未细分类对象 |
| furniture | furniture | app.models.things.furniture | Furniture | world_object | 家具；F02 `entity_kind: item` |
| access_terminal | access_terminal | app.models.things.terminals | AccessTerminal | — | 门禁/接入终端 |
| npc_agent | npc_agent | app.models.things.agents | NpcAgent | — | NPC 语义节点 |
| logical_zone | logical_zone | app.models.things.zones | LogicalZone | — | 逻辑区域/围栏 |

**说明**：`db_node_type_code` 与 F03 `graph_profile.map_node_type` 输出一致；当前 HiCampus 为 **1:1**（无别名压扁）。

## 维护

- 新增可区分语义实体时：先在本表增行，再改 `node_types`（SQL + `ensure_graph_seed_ontology`）、`graph_profile`、F02 数据与 `validator.ALLOWED_ENTITY_TYPE_CODES`。
- 变更本表时同步更新 [TYPECLASS_ONTOLOGY_PR_WORK_PLAN.md](../../../../architecture/TYPECLASS_ONTOLOGY_PR_WORK_PLAN.md) 相关 PR 备注（若有）。
