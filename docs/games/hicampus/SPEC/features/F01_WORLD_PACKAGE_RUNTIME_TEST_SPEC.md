# F01 - World Package Runtime Test SPEC

## Goal

基于项目既有测试框架（`pytest` + markers + `backend/tests/conftest.py`），为 `F01_WORLD_PACKAGE_RUNTIME` 提供可执行、可追踪、可回归的测试规范与用例清单。

## Scope

- 覆盖 `GameLoader` / `WorldInstallerService` / `GameEngineManager` 的 F01 契约行为
- 覆盖结构化返回、状态机推进、错误码、并发防抖
- 覆盖 DB 控制面契约（`world_runtime_states` / `world_install_jobs`）的最小验证路径

## Out of Scope

- F02 数据包内容完整性（数据文件质量）
- F03 语义图节点实例化正确性
- F04 管理命令端到端交互

## Test Strategy

- **Unit（主）**：隔离 DB 与外部依赖，验证契约与状态推进逻辑
- **Integration（补）**：验证 schema/migration 与持久层可读写行为
- **Regression（持续）**：围绕错误码与并发行为建立稳定回归集

## Test Markers and Paths

- 路径：`backend/tests/game_engine/test_world_package_runtime.py`
- 标记：
  - `@pytest.mark.game`
  - `@pytest.mark.unit`（无真实 DB）
  - `@pytest.mark.integration`（仅对 DB 持久化链路）

## Runtime Contract Coverage Matrix

| Case ID | 场景 | 预期 |
|---|---|---|
| F01-U-001 | `OperationResult.to_dict()` | 固定结构键齐全（`ok/world_id/job_id/status_before/status_after/error_code/message/details`） |
| F01-U-002 | `discover_games()` 扫描包目录 | 仅返回具备 `manifest.yaml` 且字段完整的包 |
| F01-U-003 | `load_game()` manifest 缺失/无效 | 返回 `WORLD_MANIFEST_INVALID` |
| F01-U-004 | `unload_game()` 稳态卸载 | 执行 `stop -> unregister -> cache cleanup`，状态为 `not_installed` |
| F01-U-005 | `run_with_job()` 成功分支 | 写入 job 成功、状态推进至 `installed`（或结果指定终态） |
| F01-U-006 | `run_with_job()` 失败分支 | 状态推进 `failed -> broken`，job 标记 `failed` |
| F01-U-007 | 并发冲突（DB 唯一窗口） | `IntegrityError` 映射为 `WORLD_BUSY` |
| F01-I-001 | schema/migration 最小校验 | `world_runtime` 表与索引存在 |
| F01-I-002 | 运行态持久化查询 | `world_runtime_states` / `world_install_jobs` 可查询状态与作业 |

## Detailed Test Cases

### Unit Cases

1. `test_operation_result_to_dict_contract`
   - 输入：构造 `OperationResult`
   - 断言：`to_dict()` 返回键完整且值一致

2. `test_discover_games_filters_invalid_manifest`
   - 准备：构造有效包、缺 `manifest.yaml` 包、manifest 缺字段包
   - 断言：仅有效包出现在 `discover_games()` 输出中

3. `test_load_game_manifest_invalid_returns_error`
   - 准备：构造无效 manifest 包，mock runtime service
   - 断言：`ok=False` 且 `error_code=WORLD_MANIFEST_INVALID`

4. `test_unload_game_executes_stop_unregister_and_cleanup`
   - 准备：预置 `loaded_games` + mock `engine.unregister_game`
   - 断言：`stop()` 被调用，缓存移除，返回 `status_after=not_installed`

5. `test_run_with_job_success_flow_updates_state_and_job`
   - 准备：mock repository + fake session context
   - 断言：调用顺序包含 `create_job -> upsert_state(enter) -> finish_job(success)`

6. `test_run_with_job_failure_flow_marks_broken`
   - 准备：`exec_fn` 返回失败结果
   - 断言：出现 `upsert_state(failed)` 与 `upsert_state(broken)`，返回 `status_after=broken`

7. `test_run_with_job_integrity_error_returns_world_busy`
   - 准备：`create_job` 抛 `IntegrityError`
   - 断言：返回 `WORLD_BUSY`，事务回滚被触发

### Integration Cases

1. `test_world_runtime_schema_exists`
   - 执行 `ensure_world_runtime_schema(engine)` 后校验两表与关键索引存在

2. `test_runtime_state_and_job_queryable`
   - 执行一次 load/unload 流程后，校验状态表与作业表可查询且字段完整

## Command Examples

```bash
cd backend
pytest tests/game_engine/test_world_package_runtime.py -m "game and unit"
pytest tests/game_engine/test_world_package_runtime.py -m "game and integration"
pytest tests/game_engine/test_world_package_runtime.py --maxfail=1 -v
```

## DoD Mapping

- F01-DoD-1（可发现包） <- `F01-U-002`
- F01-DoD-2（加载失败不影响入口） <- `F01-U-003` + manager 错误返回校验
- F01-DoD-3（卸载清理后可再加载） <- `F01-U-004` + reload 回归
- F01-DoD-4（结构化结果） <- `F01-U-001`
- F01-DoD-5（状态/作业可查询） <- `F01-I-001` + `F01-I-002`

## Risks and Notes

- 当前环境可能缺少 `pytest` 可执行命令；CI 与开发机需保证 `requirements/dev.txt` 已安装。
- 并发用例建议优先做“冲突结果契约”断言，避免脆弱的时序依赖。
