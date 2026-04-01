# F03 - Graph Seed Pipeline Test SPEC

## Goal

为 F03 提供可执行、可回归的 pytest 清单，对齐 F01/F02 测试 SPEC 风格。

## Paths & Markers

- 主文件：`backend/tests/game_engine/test_graph_seed_pipeline.py`
- 标记：`@pytest.mark.game`、`@pytest.mark.unit` / `@pytest.mark.integration`

## Coverage Matrix

| Case ID | 类型 | 场景 | 预期 |
|---------|------|------|------|
| F03-U-001 | unit | UUIDv5 确定性 | 同 `world_id`+`package_node_id` 生成相同 UUID |
| F03-U-002 | unit | profile 缺映射 | 抛出/返回 `GRAPH_SEED_TYPE_UNKNOWN` |
| F03-U-003 | unit | `connects_to` 已双向声明 | 不重复生成第四条边 |
| F03-I-001 | integration | PostgreSQL 完整 seed | 节点与关系计数 > 0；查询 `relationships` 唯一索引不冲突 |
| F03-I-002 | integration | 二次执行 pipeline | `nodes_skipped` / `relationships_skipped` 上升，无 IntegrityError |

## Commands

```bash
cd backend
conda activate campusworld
pytest tests/game_engine/test_graph_seed_pipeline.py -m "game and unit" -q
pytest tests/game_engine/test_graph_seed_pipeline.py -m "game and integration" -q
```

非 PostgreSQL 环境：`F03-I-*` 自动 `skip`。

## DoD Mapping

- F03 DoD 幂等 <- F03-I-002
- 双向边 <- F03-I-001 + 对 `connects_to` 成对断言
