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

- `world.yaml`
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

### Relationship extensions

- 在 `contains/connects_to/located_in` 之外支持：
  - `governs`, `applies_to`, `enables`, `requires`, `executes`, `located_in_zone`

## Validator Layers (L1-L5)

- L1 文件存在性：空间层+实体层+概念层
- L2 结构合法性：YAML/schema/required fields；**Entity/Concept 最小字段**（含 `presentation_domains`、`access_locks`、`source_ref`、`concept_type`、`definition` 等）
- L3 引用完整性：楼层/房间/关系端点/概念绑定；**关系端点可包含空间节点、zone、NPC、物品及概念 id**
- L4 业务基线：**HiCampus profile（写死校验）**：F1~F6 楼层数 `23/3/6/7/3/9`、`hicampus_gate` / `hicampus_bridge` / `hicampus_plaza` 必须存在；其他世界复用 F02 时应替换为可配置 profile 或独立 validator 模块
- L5 语义一致性：`rel_type_code` **白名单**（含 SPEC 所列扩展类型）；`scope: zone` 的概念应至少绑定一个 zone id；概念 `bindings` 可指向其他概念（如 skill → process）

## Schema Version Gate

- `package_meta.schema_version` 必须为当前工具链支持的整数集合（HiCampus 实现为 `2`）；不兼容时返回 `WORLD_DATA_SCHEMA_UNSUPPORTED`。

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
- F02 -> F03：输出 `PackageSnapshotV2`（`spatial/entities/concepts/relationships/meta`）
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
