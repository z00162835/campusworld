# 数据库 / 图模型验收检查表

与 CampusWorld 当前 **PostgreSQL 图库**（`nodes` / `relationships` / `node_types` / `relationship_types`）及 **F01 trait** 对齐；旧版 `graph_nodes` / `graph_edges` 描述已废弃。

## 初始化与 Schema

- [ ] `init_database.py`（或等价迁移流程）执行成功
- [ ] 扩展：`uuid-ossp`、`postgis`、`vector` 可用（与 `ensure_required_extensions` 一致）
- [ ] 四张本体/实例表存在，且含 `trait_class`、`trait_mask`、`CHECK (trait_mask >= 0)`
- [ ] 实例表触发器：`sync_*_traits_from_type`（写入时从类型表覆盖 trait）
- [ ] `trait_sync_jobs` 表及类型表上的入队触发器已创建（若运行了 `ensure_graph_schema`）

## 种子与本体

- [ ] `seed_data.py`（按需）执行成功；`account` 等 `node_types` 存在
- [ ] `ensure_graph_seed_ontology` 后，图种子相关 `node_types` / 关系类型 `connects_to` 等 trait 与 F01 / YAML 一致
- [ ] HiCampus：`world validate hicampus` 通过（含 mapped 类型的 trait 档案）

## Trait 一致性

- [ ] `db.trait_migration_check.run_trait_migration_checks()`：`node_type_mismatch` 与 `relationship_type_mismatch` 为 0（被测库已回填或仅空库）
- [ ] （可选）运行 `scripts/process_trait_sync_jobs.py` 后，无长期 `pending`/`failed` 的同步任务（若有类型变更）

## API / 查询

- [ ] `GET /api/v1/accounts`：`required_any_mask` / `required_all_mask` 为 0 时不过滤；非 0 时按位过滤（OpenAPI 含说明）
- [ ] 通过 `type_code` 查询 `nodes` 成功
- [ ] 通过 `source_id` / `target_id`（或业务封装）查询 `relationships` 成功

## 自动化测试（CI 建议）

- [ ] `pytest -m unit` 含 `tests/constants/test_trait_mask.py`、`tests/models/test_trait_query_helpers.py`、`tests/db/test_trait_migration_check.py`
- [ ] 具备 PostgreSQL 的环境：`pytest tests/db/test_trait_inheritance.py -m integration`
