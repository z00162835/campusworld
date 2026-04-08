# 图种子 `node_types` 矩阵（`type_code` ↔ 实现 ↔ 父类型）

## 设计原则（目标态）

**`node_types.parent_type_code` 应与 Python 模型「直接父类」在类型表中的代表一致**：

- 直接继承 [`DefaultObject`](../../backend/app/models/base.py) 的模型 → 父类型为 **`default_object`**（需在 `node_types` 中注册对应行，`typeclass` 指向 `DefaultObject`）。
- 直接继承 [`WorldThing`](../../backend/app/models/things/base.py) 的模型 → 父类型为 **`world_thing`**（`WorldThing` 的注册行，父为 `default_object`）。
- 直接继承 **`Furniture`** 的子类（如 `ConferenceSeating`、`LoungeFurniture`）→ 父类型为 **`furniture`**。

**说明**：这里的「父类型」是 **本体类型树**，用于治理、UI、校验；**不要求** Python 采用多重继承去模仿表结构。`WorldObject` 与 `world_object` 仅对应「**type_code 恰好为 `world_object` 的节点**」所绑定的类；**不应**因为历史原因把所有 `DefaultObject` 子类都挂在 `world_object` 下。

## 目标 `parent_type_code`（与 Python 一致）

| type_code | 目标 parent_type_code | Python 直接父类 | classname | module_path |
|-----------|----------------------|-----------------|-----------|-------------|
| `default_object` | — | — | （注册用，见 `GRAPH_SEED_ONTOLOGY_NODE_ROWS`） | `app.models.base` |
| `world_thing` | `default_object` | `DefaultObject` | `WorldThing` | `app.models.things.base` |
| `world` | `default_object` | `DefaultObject` | `World` | `app.models.world` |
| `world_object` | `default_object` | `DefaultObject` | `WorldObject` | `app.models.world` |
| `building` | `default_object` | `DefaultObject` | `Building` | `app.models.building` |
| `building_floor` | `default_object` | `DefaultObject` | `BuildingFloor` | `app.models.building` |
| `room` | `default_object` | `DefaultObject` | `Room` | `app.models.room` |
| `world_entrance` | `default_object` | `DefaultObject` | `WorldEntrance` | `app.models.world_entrance` |
| `furniture` | `world_thing` | `WorldThing` | `Furniture` | `app.models.things.furniture` |
| `npc_agent` | `world_thing` | `WorldThing` | `NpcAgent` | `app.models.things.agents` |
| `logical_zone` | `world_thing` | `WorldThing` | `LogicalZone` | `app.models.things.zones` |
| `access_terminal` | `world_thing` | `WorldThing` | `AccessTerminal` | `app.models.things.terminals` |
| `network_access_point` | `world_thing` | `WorldThing` | `NetworkAccessPoint` | `app.models.things.devices` |
| `av_display` | `world_thing` | `WorldThing` | `AvDisplay` | `app.models.things.devices` |
| `lighting_fixture` | `world_thing` | `WorldThing` | `LightingFixture` | `app.models.things.devices` |
| `conference_seating` | `furniture` | `Furniture` | `ConferenceSeating` | `app.models.things.seating` |
| `lounge_furniture` | `furniture` | `Furniture` | `LoungeFurniture` | `app.models.things.seating` |

## 迁移实现（与上表一致）

[`ensure_graph_seed_ontology`](../../backend/db/schema_migrations.py) 使用模块常量 **`GRAPH_SEED_ONTOLOGY_NODE_ROWS`**（插入顺序满足 `parent_type_code` 外键），其 `parent_type_code` 与上表「目标」列一致；单测 [`tests/db/test_graph_seed_ontology_matrix.py`](../../backend/tests/db/test_graph_seed_ontology_matrix.py) 与集成测 `test_ensure_graph_seed_ontology_parent_type_codes_match_python_mro` 校验。

**Evennia 类比**：每行仍是独立 `type_code`；`WorldThing` 在 Python 上是设备/家具等 **共同基类**，在类型树中对应 **`world_thing`**，而不是用 **`world_object`** 代替所有子类。

**`schema_definition` 扩展**：见 [`graph_seed_node_types.yaml`](../../backend/db/ontology/graph_seed_node_types.yaml)。

**任务索引**：见 [`ONTOLOGY_OPTIMIZATION_TASKS.md`](./ONTOLOGY_OPTIMIZATION_TASKS.md)。
