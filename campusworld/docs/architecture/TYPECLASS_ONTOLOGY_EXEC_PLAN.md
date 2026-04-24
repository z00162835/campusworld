# Typeclass 本体对齐 — 执行计划与优化任务

> **目标**：在严格遵守 CampusWorld 分层架构与世界包边界的前提下，将「设备 / 物品 / 车辆 / 灯具」等**可区分语义实体**从泛化 `DefaultObject` 提升为 **Evennia 风格的三层 typeclass 体系**（DB 本体行 + 引擎默认行为 + 可导入的薄子类），并与 F02 `type_code`、F03 图种子、`node_types` 表一致对齐。

## 1. 必须遵守的架构约束

下列约束与 [docs/architecture/README.md](README.md) 及根目录 `CLAUDE.md` 一致，**执行任务时不得违反**。

| 约束 ID | 要求 |
|---------|------|
| C-01 | **万物皆节点**：持久化语义仍以 `nodes` / `relationships` 为事实表；新增类型**不**为世界业务单独再建平行业务表。 |
| C-02 | **关系即语义**：空间包含、连通、位于等仍以 `relationships` + `relationship_types` 表达。 |
| C-03 | **世界内容与系统种子解耦**：HiCampus 实体定义仍在 `app/games/hicampus/data/`，**不**写入 `db/seed_data.py` 的全局最小种子。 |
| C-04 | **F02 / F03 边界**：F02 只产出校验后的数据与快照；**写库幂等策略在 F03**（或世界包 `seed_graph` 委托的 pipeline），避免在命令层随意散落 DML。 |
| C-05 | **GameLoader 解耦**：世界特定映射留在世界包（如 `graph_profile`、Python typeclass 模块）；引擎层只保留通用契约（如 `graph_seed`、profile Protocol）。 |
| C-06 | **结构化错误**：加载/种子失败继续返回稳定错误码（`WORLD_*` / `GRAPH_SEED_*`），不得吞异常拖垮入口。 |
| C-07 | **类型扩展优先走本体**：对外区分语义优先用 `node_types.type_code` + `typeclass` 路径 + `parent_type_code` 层级；**禁止**把可区分类型长期仅塞进 JSONB 而无本体行。 |
| C-08 | **Python 类名全局唯一**：与 [Evennia Typeclasses](https://www.evennia.com/docs/latest/Components/Typeclasses.html) 一致，避免重复定义同名 typeclass 类导致解析歧义。 |

## 2. Evennia 参考（实现层面应对齐什么）

官方文档：[Typeclasses](https://www.evennia.com/docs/latest/Components/Typeclasses.html)、[Objects](https://www.evennia.com/docs/latest/Components/Objects.html)。

| Evennia 概念 | CampusWorld 落点 | 说明 |
|--------------|------------------|------|
| Level 1：DB 模型（ObjectDB 等） | `nodes` + `node_types` / `relationship_types` | 一行 `node_types` ≈ 一种可实例化类型的「注册表项」。 |
| Level 2：`DefaultObject` / `DefaultRoom` … | `DefaultObject`、`Room`、`World` 等 | 引擎/模型层默认行为与 hook 基线。 |
| Level 3：目录薄子类（`Object`、`Room`、`Character`） | `app.models.things.*` 或世界包 `types.*`（须可被 import） | **设备/灯/车等应落在此层**，而非继续指向裸 `DefaultObject`。 |
| `typeclass_path` 字符串 | `node_types.typeclass` + `module_path` + `classname` | 与 Evennia「点分路径、可 `create_object(path)`」同构；新增模块须在应用启动或包加载时被 import，否则运行时解析不到（Evennia 文档：**未 import 的模块不会被 typeclass/list 发现**）。 |
| `ObjectParent` 共性 Mixin | 可选：`WorldThing(DefaultObject)` → `Light`、`Vehicle` | 减少重复 hook，保持单一继承树清晰。 |

**不清楚时的检索关键词**：`evennia typeclasses`, `evennia DefaultObject`, `evennia create_object typeclass`。

## 3. 现状问题（摘要）

- 空间侧已有较清晰的 `world` / `building` / `building_floor` / `room` 等与 ORM 类型的对应。
- **实体侧**（终端、家具、NPC、区域等）在 `ensure_graph_seed_ontology` / 初始 SQL 中，多行 **`typeclass` 指向 `app.models.base.DefaultObject`**，导致：
  - F02 的细粒度 `type_code`（如 `access_terminal`、`world_object`）在行为层**无法**绑定到独立 Python 类；
  - 与 Evennia「一种可区分对象 → 一种可加载 typeclass」不一致，后续命令/Agent/IoT 联动缺少稳定扩展点。

## 4. 目标态（验收口径）

1. 每一种需要在行为层区分的 F02 `type_code`（灯、车、门禁终端、家具……）在 `node_types` 中有**独立** `type_code` 行，且 `typeclass` 指向**继承 `DefaultObject` 的具体类**（允许中间父类 `WorldThing` / `Device`）。
2. `parent_type_code` 表达本体树（示例：`light` → `item`，`access_terminal` → `device`），供 schema 默认、管理端与校验继承使用。
3. F03 `graph_profile.map_node_type`：**F02 package `type_code` → 上述 `node_types.type_code` 1:1 或受控别名表**，避免多语义压扁到单一 `world_object` + `DefaultObject`。
4. 运行时（若已有 Node→Python hydration）：按 `node_types` 解析 **import 路径**，失败再回退 `DefaultObject`，并记录结构化日志。

## 5. 执行阶段与任务分解

### 阶段 A — 约定与登记（文档 + 注册表）

| 任务 ID | 内容 | 产出 |
|---------|------|------|
| A-1 | 建立 **「F02 type_code ↔ node_types.type_code ↔ Python typeclass 路径」** 对照表（单一事实来源） | `docs/games/hicampus/SPEC/features/` 下新文档或在 F02 SPEC 增「类型登记」附录 |
| A-2 | 在 HiCampus `INDEX.md` 或架构 README **规范索引**中挂链该对照表 | 避免口径分叉 |
| A-3 | 定义 **命名规范**：`type_code` 小写蛇形；Python 类 PascalCase；模块路径与 `app.models` / 世界包边界一致 | 写入对照表首段 |

### 阶段 B — Python typeclass 层（Evennia Level 3）

| 任务 ID | 内容 | 产出 |
|---------|------|------|
| B-1 | 新增可选中间基类 `WorldThing(DefaultObject)`（或 `Device` / `Fixture`），承载共性属性/空 hook | `backend/app/models/things/base.py`（路径可调整，须全局唯一类名） |
| B-2 | 为 HiCampus 当前数据已出现的类型各增 **薄子类**（例：`AccessTerminal`、`NpcAgent`、`LogicalZone`；按需 `Light`、`Vehicle`、`Furniture`） | 每类一个模块或分组模块 |
| B-3 | 在 **应用或世界包加载路径**中 `import` 上述模块，保证运行时可解析（对齐 Evennia「必须被 import」） | `app/models/__init__.py` 或 `games/hicampus/__init__.py` 显式导入 |

### 阶段 C — 本体库（`node_types` 行）

| 任务 ID | 内容 | 产出 |
|---------|------|------|
| C-1 | 更新 `db/schemas/database_schema.sql`：`INSERT` 每类一行，`typeclass`/`module_path`/`classname` 指向 B-2 类；设置合理 `parent_type_code` | 可重复执行的幂等 SQL |
| C-2 | 同步 `db/schema_migrations.py` 中 `ensure_graph_seed_ontology`（或独立 `ensure_node_type_ontology`），使**旧库**补齐新行 | 与 C-1 语义一致 |
| C-3 | 对已从 `DefaultObject` 迁出的旧 `type_code`，保留过渡期双读或一次性数据迁移脚本（按 `attributes`/`tags` 推断） | 迁移说明 + 可选脚本 |

### 阶段 D — F02 数据与校验

| 任务 ID | 内容 | 产出 |
|---------|------|------|
| D-1 | `entities/*.yaml`：将「灯 / 车 / …」从泛化 `world_object` **逐步改为**独立 `type_code`（与对照表一致） | 数据 PR |
| D-2 | `validator`：`type_code` 白名单与对照表 / `node_types` **对齐**（或从生成文件同步） | 防止漂移 |
| D-3 | 更新 F02 测试与测试 SPEC 中的类型相关用例 | 回归绿 |

### 阶段 E — F03 与运行时

| 任务 ID | 内容 | 产出 |
|---------|------|------|
| E-1 | 更新 `graph_profile._PACKAGE_TO_DB_NODE_TYPE`：**去掉**多对一压扁；每个 F02 `type_code` 映射到 C-1 中的独立行 | `graph_profile.py` |
| E-2 | `run_graph_seed` 创建节点时写入的 `nodes.type_code` 与本体一致；必要时写入 `attributes.entity_kind` 与 F02 一致 | pipeline 小改 + 测试 |
| E-3 | **Hydration**（若项目已有 Node→DefaultObject 工厂）：按 `node_types.typeclass` 动态 import；失败回退并打日志 | `models/` 或 `game_engine/` 内集中工厂 |
| E-4 | pytest：单元（import 路径、map_node_type）、集成（PG 种子后 `nodes.type_code` 与 typeclass 行一致） | `tests/models/` 或 `tests/game_engine/` |

### 阶段 F — 联调与治理

| 任务 ID | 内容 | 产出 |
|---------|------|------|
| F-1 | 更新 `F03_GRAPH_SEED_PIPELINE.md`：增加「类型本体与 typeclass」一小节，指向本执行计划 | 文档 |
| F-2 | CI：可选检查「新增 F02 type_code 必须在对照表中有登记」 | lint 或脚本 |
| F-3 | Code review 检查清单：C-01～C-08 | PR 模板或 reviewer 笔记 |

## 6. 建议时间顺序（里程碑）

```text
A（约定） → B（Python 类） → C（node_types 行） → E1/E2（profile + pipeline）
    → D（数据 + validator） → E3（hydration，若需要） → F（文档与 CI）
```

**说明**：C 与 B 可并行，但 **C 的 SQL 必须在 B 的类存在且可 import 之后**再合入主线，避免指向无效路径。

## 7. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 旧数据 `type_code` 与新版不一致 | C-3 迁移 + 过渡期 profile 别名 |
| 循环 import | 薄子类仅依赖 `DefaultObject` / 中间基类；避免 things → game_engine 反向依赖 |
| typeclass 路径拼写错误 | 单元测试 `importlib.import_module` + 启动时可选自检 |
| 世界包与全局模型职责争议 | **跨世界复用**放 `app/models/things/`；**仅 HiCampus** 放 `games/hicampus/types/`，但须在包 `__init__` 中 import 以满足 C-05/C-08 |

## 8. 完成定义（DoD）

- [ ] 对照表（A-1）与代码中 `node_types` / `graph_profile` / F02 白名单 **三方一致**。
- [ ] 至少一类原 `DefaultObject` 实体（如 `access_terminal`）已改为 **独立 Python 子类 + 独立 `node_types` 行**，且 F03 种子后 DB 中 `typeclass` 字段非 `DefaultObject`。
- [ ] 文档与架构 README 索引已更新；pytest 覆盖新增路径与种子回归。

## 9. 参考资料

- Evennia — [Typeclasses](https://www.evennia.com/docs/latest/Components/Typeclasses.html)
- Evennia — [Objects](https://www.evennia.com/docs/latest/Components/Objects.html)
- 本项目 — [架构 README — 可插拔世界包约束](README.md)（F01/F02/F03 边界）
- 本项目 — `backend/app/models/base.py`（`DefaultObject`）
- 本项目 — `backend/db/schemas/database_schema.sql`（`node_types`）

---

**文档维护**：本文件为**执行计划与任务清单**；具体字段级契约仍以各特性 SPEC（F02/F03）为展开来源，避免重复全文。

**按 PR 拆分的工作计划**（合并顺序、每 PR 范围与验收）：见 [TYPECLASS_ONTOLOGY_PR_WORK_PLAN.md](TYPECLASS_ONTOLOGY_PR_WORK_PLAN.md)。
