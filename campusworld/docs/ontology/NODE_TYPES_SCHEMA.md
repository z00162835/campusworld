# node_types.schema_definition 约定

与 [`backend/db/schemas/README.md`](../../backend/db/schemas/README.md) 一致：`schema_definition` 根为 JSON Schema 的 `type: object`，`properties` 的 **key 与 `nodes.attributes` 顶层键对齐**；`value_kind`、`mutability` 等与 `type`/`enum` **同级并列**。

### examine / look 展示（可选元数据）

- 根对象 **`description`**：无显式长描述时，可作为设备类 examine 的**开头段**（与 JSON Schema 标准一致）。
- 各属性 **`title`**：有则用作展示标签；无则展示 **property key**（动态属性名）。
- **`x_look: omit`**：该属性不参与 schema 驱动的 examine 列表。
- 实现见 [`app/models/things/schema_look_desc.py`](../../backend/app/models/things/schema_look_desc.py)，由 [`DefaultObject.get_display_desc` / `build_synthetic_look_desc`](../../backend/app/models/base.py) 在穷尽显式描述字段后调用；**任意** `type_code` 只要有 graph-seed schema 即参与 examine 合成。子类可重写 `_attributes_for_schema_look`（如照明将 `power_on` 映射为 `status`）。运行时优先读打包 YAML 缓存（与 DB 中 `node_types.schema_definition` 应对齐，迁移后一致）。

## 图种子本体扩展文件

- 路径：[`backend/db/ontology/graph_seed_node_types.yaml`](../../backend/db/ontology/graph_seed_node_types.yaml)
- 由 [`ensure_graph_seed_ontology`](../../backend/db/schema_migrations.py) 读取；**每次迁移执行**会对 `node_types` 做 `ON CONFLICT DO UPDATE`，**覆盖**该文件中声明类型的 `schema_definition`、`schema_default`、`inferred_rules`、`tags`、`ui_config`（未在文件中出现的 `type_code` 仍写入空 JSON，与历史行为一致）。
- 顶层 `schema_revision`：整数，仅供人工/文档追踪；**不参与**条件更新逻辑。

## 独立 type_code（Evennia 类比）

`network_access_point`、`access_terminal`、`lighting_fixture` 等为 **独立本体类型**，Python 上可共享 [`WorldThing`](../../backend/app/models/things/base.py) 行为基类，但 **DB `type_code` 与 YAML 中 schema 块均按类型分立**，不合并为单一「设备大类型」。

## 类型矩阵与父类型原则

图种子涉及的 `type_code`、父类型与 Python 类见 [`GRAPH_SEED_NODE_TYPES_MATRIX.md`](./GRAPH_SEED_NODE_TYPES_MATRIX.md)。**`parent_type_code` 应与 Python 直接父类在类型表中的代表一致**（`DefaultObject` → `default_object`，`WorldThing` → `world_thing`）；由 `ensure_graph_seed_ontology` 与 **`GRAPH_SEED_ONTOLOGY_NODE_ROWS`** 保证。

## 任务与测试索引

见同目录 [`ONTOLOGY_OPTIMIZATION_TASKS.md`](./ONTOLOGY_OPTIMIZATION_TASKS.md)。
