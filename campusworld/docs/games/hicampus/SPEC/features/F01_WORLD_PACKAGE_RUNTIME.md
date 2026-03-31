# F01 - World Package Runtime

## Goal

建立 `HiCampus` 作为独立 world package 的运行时能力，支持发现、加载、卸载、重载，并提供可持久化的运行状态与作业记录。

## Scope

- `games/hicampus` 包结构与入口契约
- 与 `GameLoader`/`GameEngineManager` 对接
- 运行时状态管理（DB 持久态 + 内存缓存）
- 结构化错误码与结构化结果输出

## Out of Scope

- 世界数据文件设计（见 `F02`）
- 图数据实例化（见 `F03`）
- 管理命令（见 `F04`）

> 约束：F01 只交付 runtime ready，不承诺业务语义节点落库；M1 端到端需联动 `F02 + F03`。

## Key Interfaces

- `discover_games()`
- `load_game("hicampus")`
- `unload_game("hicampus")`
- `reload_game("hicampus")`

## Package Contract (Strong Validation)

世界包目录必须包含：

- `__init__.py`
- `game.py`
- `manifest.yaml`
- `get_game_instance`（可调用）

`manifest.yaml` 必填字段：

- `world_id`
- `version`
- `api_version`
- `data_dir`

缺失任一字段，返回 `WORLD_MANIFEST_INVALID`。

## Runtime States (V2)

- `not_installed`
- `installing`
- `loading`
- `installed`
- `unloading`
- `reloading`
- `failed`
- `broken`

状态来源：

- `world_runtime_states`：最终状态与最近错误
- `world_install_jobs`：过程作业、事件日志、结果摘要

## Structured Result Contract

```json
{
  "ok": true,
  "world_id": "hicampus",
  "job_id": "uuid",
  "status_before": "not_installed",
  "status_after": "installed",
  "error_code": null,
  "message": "world loaded",
  "details": {}
}
```

## Error Codes (minimum)

- `WORLD_NOT_FOUND`
- `WORLD_NOT_INSTALLED`
- `WORLD_MANIFEST_INVALID`
- `WORLD_STATE_CONFLICT`
- `WORLD_DB_WRITE_FAILED`
- `WORLD_DB_ROLLBACK_FAILED`
- `WORLD_LOAD_FAILED`
- `WORLD_UNLOAD_FAILED`
- `WORLD_RELOAD_FAILED`
- `WORLD_BUSY`
- `WORLD_INTERNAL_ERROR`

## Dependencies

- 前置：无
- 被依赖：`F03` `F04` `F05` `F06`

## DoD

- 可发现 `hicampus` 包
- 加载失败时不影响系统入口会话
- 卸载后资源清理完成且可再次加载
- 所有运行时操作返回结构化结果（不兼容旧 `None/False`）
- 状态与作业可在 DB 查询（`world_runtime_states`、`world_install_jobs`）

## Validation Plan (V2)

- 用例 1：`discover_games()` 仅返回包含 `manifest.yaml` 且字段完整的世界包。
- 用例 2：`load_game("hicampus")` 成功后：
  - 返回 `ok=true`
  - `status_after=installed`
  - `world_runtime_states.status=installed`
  - `world_install_jobs` 有 `action=load` 且 `status=success`
- 用例 3：manifest 缺字段时：
  - 返回 `WORLD_MANIFEST_INVALID`
  - `world_runtime_states.status=broken`
  - `world_install_jobs.status=failed`
- 用例 4：`unload_game("hicampus")` 时必须执行 `stop -> unregister -> cache cleanup`。
- 用例 5：`reload_game("hicampus")` 失败时落 `failed -> broken`，并保留错误码。
- 用例 6：并发触发同一世界操作时返回 `WORLD_BUSY`。
- 用例 7：DB 写入失败时返回 `WORLD_DB_WRITE_FAILED`，系统入口会话不崩溃。
- 用例 8（联调项，非 F01 单独验收）：F03 生效后校验 DB 语义节点网络可查询（`world/gate/bridge/plaza/buildings`）。
