# F02 - World Data Package Test SPEC (Dual-Model)

## Goal

验证 F02 双模型数据包（实体=事实，概念=抽象）在文件、结构、语义、迁移与集成上的可用性与可回归性。

## Scope

- `games/hicampus/data` 的空间层/实体层/概念层文件契约
- `PackageSnapshotV2` 装载与校验
- world-scoped migration 的 dry-run 计划构建
- F01 预加载校验返回 `WORLD_DATA_*` 错误码

## Test Matrix

| Case ID | 类型 | 场景 | 预期 |
|---|---|---|---|
| F02-U-001 | unit | `validate_data_package` 正常路径 | 返回 `world/spatial/entities/concepts/relationships/meta` |
| F02-U-002 | unit | `load_package_snapshot` | 生成 `PackageSnapshotV2` 且双模型字段齐全 |
| F02-U-003 | unit | `build_migration_plan` | 返回可执行迁移计划（含 operations） |
| F02-U-004 | unit | loader 加载 `hicampus` | `details.package.world_data_validated=true`、`snapshot_loaded=true` 且含统计 |
| F02-U-005 | unit | 缺失关键数据文件 | `WORLD_DATA_UNAVAILABLE` |
| F02-U-006 | unit | 关系端点含 NPC | `located_in` 等关系的 `source_id`/`target_id` 可为实体 id |
| F02-U-007 | unit | `schema_version` 不兼容 | `WORLD_DATA_SCHEMA_UNSUPPORTED` |
| F02-U-008 | unit | 非法 `rel_type_code` | `WORLD_DATA_SEMANTIC_CONFLICT` |
| F02-U-009 | unit | `migration_dry_run` | `operation_preview` 非空且 `post_validate` 标记当前包合法 |
| F02-U-010 | unit | `validate_world_data_package('hicampus')` | 返回与 `validate_data_package` 等价的 payload |
| F02-I-001 | integration | F01 + F02 | `load_game` 在数据包损坏时返回 `WORLD_DATA_*` |
| F02-I-002 | integration | F02 + F03（后续） | F03 消费 `PackageSnapshotV2` 幂等落库 |

## Acceptance Checklist

- [ ] `seed_minimal` 不创建 HiCampus 业务节点
- [ ] 缺失文件返回明确 `WORLD_DATA_UNAVAILABLE`
- [ ] 引用断裂返回 `WORLD_DATA_REFERENCE_BROKEN`
- [ ] 语义冲突返回 `WORLD_DATA_SEMANTIC_CONFLICT`
- [ ] 迁移计划支持 world-scoped dry-run
- [ ] F01 能透传 F02 的 `WORLD_DATA_*` 错误码（含 `WORLD_DATA_SCHEMA_UNSUPPORTED`）
- [ ] 无 `load_package_snapshot` 的世界包在具备 `package.validator` 时仍无法绕过全量校验（由 `validate_world_data_package` 保证）

## Commands

```bash
cd backend
pytest tests/game_engine/test_hicampus_data_package.py -m "game and unit" -v
pytest tests/game_engine/test_world_package_runtime.py tests/game_engine/test_hicampus_data_package.py -m game -v
```

