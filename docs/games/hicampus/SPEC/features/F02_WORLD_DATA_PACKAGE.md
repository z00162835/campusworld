# F02 - World Data Package

## Goal

定义 `HiCampus` 独立数据目录与数据文件规范，确保与全局 `seed_data.py` 解耦。

## Scope

- `games/hicampus/data/*` 文件组织与版本化
- world-scoped migration 规则
- 数据完整性基础校验（文件级）

## Out of Scope

- 节点写库逻辑（见 `F03`）
- 命令交互（见 `F04`）

## Data Files

- `world.yaml`（含 `world` 与 **`world_environment`** 块，HiCampus 必填后者）
- `buildings.yaml`
- `floors.yaml`
- `rooms.yaml`
- `relationships.yaml`

## Dual-Model Semantics (V2)

- **EntityModel（事实模型）**：物理世界语义化实体，强调可定位、可交互、可实例化。
  - 示例：`npc_agent`、`access_terminal`、`furniture`、`logical_zone`
- **ConceptModel（概念模型）**：抽象治理语义，强调可绑定、可约束、可推理。
  - 示例：`goal`、`process`、`rule`、`behavior`、`skill`

## Directory Layout (V2)

```text
games/hicampus/data/
  ├── world.yaml
  ├── buildings.yaml
  ├── floors.yaml
  ├── rooms.yaml
  ├── relationships.yaml
  ├── entities/
  │   ├── npcs.yaml
  │   ├── items.yaml
  │   └── zones.yaml
  ├── concepts/
  │   ├── goals.yaml
  │   ├── processes.yaml
  │   ├── rules.yaml
  │   ├── behaviors.yaml
  │   └── skills.yaml
  ├── package_meta.yaml
  └── migrations/
```

## Data Contract

### EntityModel minimum

- `id`, `type_code`, `entity_kind`, `display_name`
- `location_ref` or `zone_ref`
- `attributes`, `tags`
- `presentation_domains`, `access_locks`
- `source_ref`

### ConceptModel minimum

- `id`, `concept_type`, `name`, `scope`, `version`
- `definition`, `bindings`
- `attributes`, `tags`, `source_ref`

### `world_environment`（HiCampus 必填）

`world.yaml` 除 `world:` 外须含 **单对象** `world_environment:`（非 entities 桶）：

- `id`, `type_code: world_environment`, `display_name`, `world_ref`（须等于 `world.id`）
- `attributes`：宏观天气/温湿度等（见 [F09](F09_WORLD_ENVIRONMENT.md)）
- `tags`

户外 room 在 `rooms.yaml` 用 tag **`environment:outdoor`** 标记（HiCampus：`hicampus_bridge`、`hicampus_plaza`；**不含** `hicampus_gate`）。`spatial_generate` 会为上述 landmark room 保留/注入该 tag。

### Relationship extensions

- 在 `contains/connects_to/located_in` 之外支持：
  - `governs`, `applies_to`, `enables`, `requires`, `executes`, `located_in_zone`

### 关系类型：校验全集 vs F03 种子子集

- **F02 validator** 对上述扩展 `rel_type_code` 做白名单与引用校验；数据包可以包含「治理/概念绑定」类关系。
- **F03 `WorldGraphProfile.allowed_relationship_type_codes`**（HiCampus 当前为 `contains` / `connects_to` / `located_in`）决定**哪些关系会写入图库**；不在集合内的关系在默认模式下被**跳过**，并在 `run_graph_seed` 的 `details.relationships_ignored_*` 中计数。
- 若 `manifest` 中 `features.graph_seed.strict_relationships: true`（或 pipeline 参数 `strict_relationships=True`），则任一未支持的关系类型会导致种子失败，错误码 `GRAPH_SEED_RELATIONSHIP_UNSUPPORTED`。
- 扩展 F03 落库类型时：同步扩展 `relationship_types` 本体、`graph_profile` 白名单，并评估是否开启 strict。

## Validator Layers (L1-L5)

- L1 文件存在性：空间层+实体层+概念层
- L2 结构合法性：YAML/schema/required fields；**Entity/Concept 最小字段**（含 `presentation_domains`、`access_locks`、`source_ref`、`concept_type`、`definition` 等）
- L3 引用完整性：楼层/房间/关系端点/概念绑定；**关系端点可包含空间节点、zone、NPC、物品及概念 id**
- L4 业务基线：**HiCampus**：楼层数与必现房间从 `package/baseline_profile.yaml` 读取（缺文件时回退内置默认值）；其他世界复用 F02 时应替换为该文件或独立 validator 模块
- L5 语义一致性：`rel_type_code` **白名单**（含 SPEC 所列扩展类型）；`scope: zone` 的概念应至少绑定一个 zone id；概念 `bindings` 可指向其他概念（如 skill → process）

## Schema Version Gate

- `package_meta.schema_version` 必须为当前工具链支持的整数集合（HiCampus 实现为 `2`）；不兼容时返回 `WORLD_DATA_SCHEMA_UNSUPPORTED`。

## 语义地图网格坐标（HiCampus）

HiCampus 为 CampusWorld 语义地图提供两层显式坐标，写入图节点 `attributes`（经 `world reload` / graph seed 落库）：

| 层级 | 属性 | 写入来源 | 用途 |
|------|------|----------|------|
| floor 平面图 | `map_grid_col`, `map_grid_row`；可选 `map_grid_span_w`, `map_grid_span_h` | `topology_connect_generate --write` 为层内 room 赋值 | `viewLayer=floor` 网格布局与层内 `connects_to` 边 |
| campus 鸟瞰 | `campus_grid_col`, `campus_grid_row`；可选 `campus_grid_span_w`, `campus_grid_span_h` | `buildings.yaml` 楼栋条目；`rooms.yaml` 户外锚点（`hicampus_gate` / `hicampus_bridge` / `hicampus_plaza`） | `viewLayer=campus` 楼栋与户外地标定位 |

约定：

- **D6**：floor 内 `map_grid_*` 由拓扑生成器维护，手工 YAML 勿与生成结果冲突。
- **D9**：campus 层 `campus_grid_*` 由数据包作者维护相对位置；缺失时 semantic map 回退水平排布。
- 户外地标间 `connects_to`（gate ↔ bridge ↔ plaza）来自 `relationships.yaml`，在 campus 层渲染为 spine 边。
- `geom_geojson` 由 graph seed pipeline 从 `map_grid_*` 同步（室内 room）；campus 层仅消费 `campus_grid_*`。

校验：`world validate hicampus` 应对 campus 层坐标缺失给出警告（实现逐步补齐）。

## 程序化生成（`package/`）

空间层、拓扑连边与部分实体/关系可由 `games/hicampus/package/` 下模块重写 YAML。**命令顺序、保留的手工关系 id、与 `world reload` 的配合**以仓库内真源为准：

- [`backend/app/games/hicampus/package/README.md`](../../../../../backend/app/games/hicampus/package/README.md)

要点：`topology_connect_generate` 会替换非保留集内的 `connects_to`；`entity_relationship_generate` 主要合并 `located_in` 等，与 `connects_to` 共存。

## Migration Strategy

- world-scoped migration 目录：`games/hicampus/data/migrations`
- 命名：`V{semver}__{slug}.yaml`
- 支持操作：
  - 空间：`add_room/update_room/remove_room`
  - 实体：`add_entity/update_entity/remove_entity/relocate_entity`
  - 概念：`add_concept/update_concept/remove_concept/rebind_concept`
  - 关系：`add_relationship/remove_relationship`
- 无 rollback 时必须 `dry-run` + 人工确认
- 实现状态：`build_migration_plan(data_root, from_version, to_version)` 按 semver 窗口筛选迁移；`migration_dry_run(..., post_validate=True)` 输出 `operation_preview` 并对**当前**数据树执行 `validate_data_package`（不修改文件；全量 YAML 写回仍为后续可选能力）

## Integration Contract

- F01 -> F02：存在 `app.games.<world_id>.package.validator` 时，`GameLoader` 在 `load/reload` 中**始终**调用 `validate_world_data_package`（见 `app/game_engine/world_data_validate.py`）；无该子模块时仅对含 `world.yaml` 的数据目录做最小五文件检查
- F02 -> F03：输出 `PackageSnapshotV2`（`spatial/entities/concepts/relationships/meta`；HiCampus 另含 **`world_environment`** 单对象，见 [F09](F09_WORLD_ENVIRONMENT.md)）
- F03 仅消费 snapshot，不直接解析 YAML

## Error Codes

- `WORLD_DATA_UNAVAILABLE`
- `WORLD_DATA_INVALID`
- `WORLD_DATA_SCHEMA_UNSUPPORTED`
- `WORLD_DATA_REFERENCE_BROKEN`
- `WORLD_DATA_BASELINE_MISMATCH`
- `WORLD_DATA_SEMANTIC_CONFLICT`

## Dependencies

- 前置：无
- 被依赖：`F03` `F06`

## DoD

- `seed_minimal` 不创建 HiCampus 业务节点
- 缺失数据文件时返回明确错误码
- 数据目录可独立升级与回滚
