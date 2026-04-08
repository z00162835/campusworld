# node_types / schema_definition 优化任务与测试

## 架构约束

- 知识本体在 **db + models/graph**，图种子在 **db/schema_migrations** 与 **game_engine/graph_seed**；不引入与 F02/F03 冲突的第二套包内 ontology 真源。
- 扩展数据放在 **`backend/db/ontology/`**，由迁移入口加载，保持 **幂等**。
- **`graph_seed_node_types.yaml`** 中的 **`schema_definition`** 经 **T3** 写入 **`node_types`**，并同时作为 **examine / `get_display_desc`** 缺省补全文案的元数据真源：运行时由 [`get_graph_seed_schema_definition`](../../backend/db/ontology/load.py) 读**进程内缓存的打包 YAML**（与 DB 在 **migrate** 后应对齐；热更 YAML 需进程重启或调用 `clear_graph_seed_node_type_cache()`）。

## 已交付

| 任务 | 说明 | 测试 |
|------|------|------|
| T1 规范文档 | `NODE_TYPES_SCHEMA.md`（含 **examine / look** 与 schema 字段约定）+ db README 交叉引用 | 文档审阅 |
| T2 YAML 真源 | `graph_seed_node_types.yaml`：设备/家具/空间等 **`schema_revision: 2`** | `tests/db/test_ontology_load.py` |
| T3 迁移写入 | `ensure_graph_seed_ontology`：`ON CONFLICT` 更新 schema 列 | `test_ensure_graph_seed_ontology_*`（graph seed 测试） |
| T4 扩展覆盖 | 已补充 `av_display`、`furniture`、`conference_seating`、`lounge_furniture`、`room`、`building`、`building_floor`、`world`、`world_object`、`npc_agent`、`logical_zone`、`world_entrance` | 同左 + `test_ensure_graph_seed_ontology_room_schema_from_yaml` |
| **schema 驱动 examine** | 无显式长描述时，[`DefaultObject.get_display_desc`](../../backend/app/models/base.py) 调用 **`build_synthetic_look_desc`**；[`app/models/things/schema_look_desc.py`](../../backend/app/models/things/schema_look_desc.py) 按 **`schema_definition.properties`** 逐条输出（根 **`description`**、属性 **`title` / key**、**`x_look: omit`**、嵌套 object）。**所有**带 graph-seed schema 的 `type_code`（Room、Building、设备、家具等）共用此路径；子类按需重写 **`_attributes_for_schema_look`**（如 [`LightingFixture`](../../backend/app/models/things/devices.py)）。约定见 [`NODE_TYPES_SCHEMA.md`](./NODE_TYPES_SCHEMA.md) **examine / look 展示** 小节。 | [`tests/models/test_schema_look_desc.py`](../../backend/tests/models/test_schema_look_desc.py)、[`tests/models/test_things_typeclasses.py`](../../backend/tests/models/test_things_typeclasses.py)（含 room / AP） |
| T7 类型矩阵 | [`GRAPH_SEED_NODE_TYPES_MATRIX.md`](./GRAPH_SEED_NODE_TYPES_MATRIX.md) | 与 **`GRAPH_SEED_ONTOLOGY_NODE_ROWS`** 一致 |
| **T9 父链对齐** | 注册 **`default_object`** / **`world_thing`**；`parent_type_code` 与 Python 直接父类一致；常量 **`GRAPH_SEED_ONTOLOGY_NODE_ROWS`** + FK 安全顺序 | `test_graph_seed_ontology_matrix.py`（单元）+ `test_ensure_graph_seed_ontology_parent_type_codes_match_python_mro`（PG 集成） |
| **T6 可选校验** | `db/ontology/attribute_schema_warn.py`：`warn_extra_attributes_vs_schema`（仅 warning，调用方自选挂载点） | `tests/db/test_attribute_schema_warn.py` |
| **T8 矩阵检查** | 单元测校验 `GRAPH_SEED_ONTOLOGY_NODE_ROWS` 的父链闭包与目标表 | `tests/db/test_graph_seed_ontology_matrix.py` |
| **T5 JSON Schema 信封** | `db/ontology/schema_envelope.py`：`flat_field_types_to_json_schema_object`、`property_fragments_to_json_schema_object`；内置类型真源 **`account_node_type_schema_definition`**、`system_command_ability_node_type_schema_definition`、`system_notice_node_type_schema_definition`；**`root_manager`**（`room` / `system_bulletin_board`）、**`seed_data.ensure_account_type`**、**`ability_sync`**、**`system_bulletin_manager`**、**`create_account_type`** 使用信封；迁移 **`ensure_builtin_node_type_schema_envelopes`**（`migrate_report` 在 `ensure_graph_seed_ontology` 之后）将已存在库中仍为 legacy 形态的 `account` / `system_command_ability` / `system_notice` 行升级为信封（已为信封则跳过） | `tests/db/test_schema_envelope.py` |

## 待办

| 任务 | 说明 | 建议测试 |
|------|------|----------|
| T6 挂载点 | 在图种子写入或 `ModelManager` 等路径 **可选调用** `warn_extra_attributes_vs_schema`（默认关闭或仅 debug） | 集成/开关策略 |
| T8 CI | 可选：在 CI 中单独跑 ontology 相关 `pytest` 子集（见下文「运行相关测试」一键命令） | 可选 |

### T9 与 `schema_default` / `inferred_rules` 等列（范围边界）

**T9 不包含**对 `node_types` 上 **`schema_definition` / `schema_default` / `inferred_rules` / `ui_config` 内容**的系统性优化或大规模补全。图种子侧这些列的**真源与幂等写入**已由 **T2–T4** 承担：`graph_seed_node_types.yaml` 声明各 `type_code` 的片段，[`ensure_graph_seed_ontology`](../../backend/db/schema_migrations.py) 在 `ON CONFLICT` 时合并更新上述 JSONB 列（见 [`NODE_TYPES_SCHEMA.md`](./NODE_TYPES_SCHEMA.md)）。

T9 文案中的「同步 `graph_seed_node_types.yaml` **若有按父类型的策略**」仅指：若产品上要按 **`parent_type_code` 继承**默认 schema / 规则，再在 YAML 或迁移里体现；**不是** T9 的默认交付项。

**`default_object` / `world_thing`** 可无 YAML 块（迁移写入空 JSONB）；需要完整 schema 块时单独立项。

## 运行相关测试

```bash
cd backend
# 本体加载 / 矩阵 / 信封 / 属性告警（无需 PG）
pytest tests/db/test_ontology_load.py tests/db/test_graph_seed_ontology_matrix.py tests/db/test_attribute_schema_warn.py tests/db/test_schema_envelope.py -v
# schema 驱动 examine（纯单元）
pytest tests/models/test_schema_look_desc.py tests/models/test_things_typeclasses.py -v
# 图种子 + ensure_graph_seed_ontology / ensure_builtin 信封（需 PostgreSQL）
pytest tests/game_engine/test_graph_seed_pipeline.py::test_ensure_graph_seed_ontology_applies_yaml_schema_definitions -v
pytest tests/game_engine/test_graph_seed_pipeline.py::test_ensure_graph_seed_ontology_room_schema_from_yaml -v
pytest tests/game_engine/test_graph_seed_pipeline.py::test_ensure_graph_seed_ontology_parent_type_codes_match_python_mro -v
pytest tests/game_engine/test_graph_seed_pipeline.py::test_ensure_builtin_node_type_schema_envelopes_idempotent -v
```

一键覆盖上述目录（仍建议 CI 全量 `pytest`）：

```bash
cd backend
pytest tests/db/test_ontology_load.py tests/db/test_graph_seed_ontology_matrix.py tests/db/test_attribute_schema_warn.py tests/db/test_schema_envelope.py tests/models/test_schema_look_desc.py tests/models/test_things_typeclasses.py tests/game_engine/test_graph_seed_pipeline.py -q
```

集成测试需要可用的 PostgreSQL（与现有 graph seed 测试相同）。
