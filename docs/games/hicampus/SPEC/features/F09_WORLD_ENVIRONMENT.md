# F09 - World Environment

## Goal

为每个 world 引入 **单例** 图节点 `type_code: world_environment`（trait_class `ENV`），承载园区级宏观天气、温湿度与模拟时间；户外 room 在 `look` 时展示环境摘要。

## Scope

- 本体：`world_environment` 类型注册（`graph_seed_node_types.yaml` + `GRAPH_SEED_ONTOLOGY_NODE_ROWS`）
- Python typeclass：`WorldEnvironment`（`app.models.things.environments`）
- HiCampus 数据：`world.yaml` 的 `world_environment:` 块（**必填**）
- F02 快照：`PackageSnapshotV2.world_environment`
- F03 种子：幂等 upsert、`location_id → world`、`mutability` 合并
- `look`：带 `environment:outdoor` tag 的 room 在描述与 `ambiance` 之间插入一行环境摘要

## Out of Scope

- 定时 tick / 天气演化（scheduler）
- `governs` 边与 `logical_zone` 联动
- 室内 HVAC 聚合
- 独立 Agent 命令（读节点走现有 `find` / `describe`）

## Node Semantics

| 字段 | mutability | 说明 |
|------|------------|------|
| `climate_profile` | `package_seed` | 气候带；reload 可被 YAML 覆盖 |
| `weather_code` | `runtime` | enum：`clear` / `cloudy` / `overcast` / `rain` / `fog` |
| `temperature_c` | `runtime` | 室外基准温度（°C） |
| `humidity_pct` | `runtime` | 相对湿度（%） |
| `wind_mps` | `runtime` | 可选风速 |
| `sim_time` | `runtime` | ISO 模拟时间 |

- **`world_ref`**（YAML 顶层）：对应 `world.id`；种子后保留于 `attributes.world_ref` 便于排查。
- **`location_id`**：运行时真源，指向 `world` 节点 id。
- **Create**：首次 seed 写入 YAML 中全部属性（含 runtime 初值）。
- **Update**：按 `node_types.schema_definition.properties.*.mutability` 合并；`runtime` 保留 DB 值，`package_seed` 取自 YAML。
- **Update（reload 语义）**：仅 `world_environment` 走完整 mutability 合并；其他 type 为浅合并，并保留 schema 中 `instance_managed` / `runtime` 键，避免 reload 洗掉 agent/device 实例态。

## HiCampus Defaults

`world.yaml` 示例见 [`backend/app/games/hicampus/data/world.yaml`](../../../../../backend/app/games/hicampus/data/world.yaml)。

户外 tag（**严格门控**，无 room_type 兜底）：

- `hicampus_bridge`
- `hicampus_plaza`

**不含** `hicampus_gate`。

## Look Integration

- 门控：`environment:outdoor` ∈ room.tags
- 解析：`resolve_world_environment(session, world_id=room.attributes.world_id)`
- 展示：`format_environment_summary` → 单行中文，如「室外：多云，28°C，湿度 72%」（随 `world.yaml` runtime 初值变化）
- 位置：room 描述正文之后、`氛围：` 之前（见 [CMD_look](../../../../command/SPEC/features/CMD_look.md)）

`spatial_generate` 在保留 `hicampus_bridge` / `hicampus_plaza` 时会注入 `environment:outdoor`，避免 regenerate 丢失 tag。

## Evennia Mapping

Evennia 常用 GLOBAL Script 持有天气状态；CampusWorld 以 **ENV 图节点 + `location_id→world`** 替代 Script 表，符合「万物皆节点」。

## Deployment

```bash
cd backend
python -m db.init_database migrate    # 刷新 node_types（含 world_environment）
# 游戏内或 admin：
world reload hicampus
```

无独立 SQL data migration；已安装环境 **migrate + reload** 即可补齐节点。

## Acceptance

- [ ] `world validate hicampus` 通过；缺 `world_environment` 或错误 `world_ref` 失败
- [ ] reload 后 `world_environment.location_id` 指向 world 节点
- [ ] 改 YAML `temperature_c` 后 reload，DB runtime **不变**
- [ ] SSH：`look` @ plaza/bridge 见环境行；gate **不见**
- [ ] F02 登记表、`GRAPH_SEED_NODE_TYPES_MATRIX` 含 `world_environment`

## Dependencies

- 前置：`F02` `F03`
- 被依赖：无（内容层可选）

## Related

- [F02_WORLD_DATA_PACKAGE.md](F02_WORLD_DATA_PACKAGE.md)
- [F03_GRAPH_SEED_PIPELINE.md](F03_GRAPH_SEED_PIPELINE.md)
- [F02_ENTITY_TYPE_REGISTRY.md](F02_ENTITY_TYPE_REGISTRY.md)
- [CMD_look](../../../../command/SPEC/features/CMD_look.md)
- [CMD_describe](../../../../command/SPEC/features/CMD_describe.md)
