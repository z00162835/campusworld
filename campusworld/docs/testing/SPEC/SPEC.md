# Testing SPEC

> **Architecture Role**: 测试工程是项目质量保障的核心基础设施，提供统一的测试框架、测试分类、命名约定和 CI 集成策略。

## Module Overview

测试系统覆盖后端 pytest 和前端 vitest 两个框架，通过统一的测试规范确保代码质量。

```
后端: pytest + pytest-asyncio + pytest-cov + pytest-mock
前端: vitest + @vue/test-utils + jsdom
```

## Test Classification

| 类型 | 框架 | 路径 | 标记 |
|------|------|------|------|
| Unit Tests | pytest | `backend/tests/test_*.py` | `@pytest.mark.unit` |
| Integration Tests | pytest | `backend/tests/test_*.py` | `@pytest.mark.integration` |
| SSH Module Tests | pytest | `backend/tests/test_ssh_*.py` | `@pytest.mark.ssh` |
| Model Tests | pytest | `backend/tests/test_models_*.py` | `@pytest.mark.models` |
| Command Tests | pytest | `backend/tests/test_commands_*.py` | `@pytest.mark.commands` |
| Component Tests | vitest | `frontend/src/**/*.spec.ts` | — |
| E2E Tests | (future) | `frontend/e2e/*.spec.ts` | `@pytest.mark.e2e` |

## Test Configuration

### 后端 pytest 配置

```ini
# backend/pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short --strict-markers
asyncio_mode = auto
```

### 后端 Python / Conda 环境

本地执行后端 `pytest` 时，应使用与项目依赖一致的 Python 环境。**仓库约定：后端开发与 pytest 以 Conda 环境 `campusworld` 为准**（见根目录 [`CLAUDE.md`](../../../CLAUDE.md)「Python 执行环境（Conda `campusworld`）」）。若未使用该环境，常见为 `ModuleNotFoundError` 或 pytest 未安装，**不代表被测代码必然有误**。

若使用 Conda 且已创建环境 **`campusworld`**，推荐在运行测试前执行：

```bash
conda activate campusworld
cd backend
pytest
```

避免默认 shell 指向 Conda **base** 或其它环境，导致缺少 `pytest`、依赖版本与 `requirements` 不一致等问题。无需持久激活时，可在 `backend` 目录下单次执行：

```bash
conda run -n campusworld pytest
```

### 验证分层与失败/超时说明

| 场景 | 命令 | 说明 |
|------|------|------|
| **快速验证（无 PostgreSQL）** | `conda run -n campusworld pytest -m "not integration and not postgres_integration"` | 同时跳过 `@pytest.mark.integration` 与 **`postgres_integration`**（后者即使未标 `integration` 也会默认收集）；避免在未启动 PostgreSQL 时长时间等待连接（引擎可对 PG 使用 `connect_timeout`，但仍会阻塞至超时）。 |
| **全量后端** | `conda run -n campusworld pytest` | 含集成测试；需 `app.core.database` 指向 **PostgreSQL**（见 `backend/config`），否则部分用例会 `skip` 或失败。 |
| **最慢用例自检** | `conda run -n campusworld pytest --durations=15` | 列出耗时最长的 15 条，便于排查「超长」。 |
| **F02 / PostgreSQL** | `conda run -n campusworld pytest -m postgres_integration` | 需可达 PostgreSQL + **pgvector**；含 `tests/db/test_agent_memory_tables.py`、`tests/commands/test_agent_f02_commands.py`（capabilities + **`run_npc_agent_nlp_tick` stub-LLM → `agent_run_records`**）、`tests/services/test_ltm_semantic_retrieval.py`（LTM 向量 + 链接扩展）等。 |
| **F03 AICO（快速）** | `conda run -n campusworld pytest tests/commands/test_npc_agent_nlp.py tests/game_engine/test_agent_llm_config.py tests/game_engine/test_llm_pdca_framework.py tests/services/test_ltm_semantic_retrieval.py -m unit -q` | `CommandResult` 形状与 **`run_npc_agent_nlp_tick`** passthrough（mock）；`prompt_overrides` / `model_config` 合并、PDCA LLM、LTM tick 摘要拼接（mock）；**不含** `test_agent_f02_commands.py` 中需 PG 的用例。 |
| **F04 `@` handle（快速）** | `conda run -n campusworld pytest tests/commands/test_npc_agent_resolve.py tests/commands/test_f04_at_dispatch.py -q` | `resolve_npc_agent_by_handle`、`try_dispatch_at_line`（mock）；不含 SSH。 |
| **配置校验** | `cd backend && python scripts/validate_config.py` | 验证 `settings*.yaml` 与 Pydantic Settings 一致。 |
| **F03 手工 SSH（DB 已迁移 + 种子）** | 登录后于奇点屋执行 `look`（应见 AICO）、`aico hello`、`@aico hello` | 见 [F03 §7 验收](../../../models/SPEC/features/F03_AICO_DEFAULT_SYSTEM_ASSISTANT.md#7-验收标准建议)。 |

**收集阶段失败（历史常见）**

- **`InvalidRequestError: Attribute name 'metadata' is reserved`**：`Declarative` 模型类上不能使用 Python 属性名 `metadata`（与 `MetaData` 冲突）。`world_runtime_states` 表若列名为 `metadata`，应使用 `state_metadata = Column("metadata", ...)` 等形式映射。
- **`Tuple` / 类型注解 `NameError`**：`typing` 中缺少 `Tuple` 等导入会导致整包收集失败；修复对应模块的 `from typing import ...` 即可。

**IDE / CI 超时**

- 全量用例数量较多时，单次 `pytest` 可能超过工具默认超时；可先跑 `-m "not integration and not postgres_integration"`，再在具备数据库的环境跑全量或 `-m postgres_integration`。

**数据库会话与 `get_db` 生成器（测试编写）**

- 手写 `SessionLocal()` 时，用 **`try` / `finally: session.close()`**（或 `with db_session_context()`）保证任意断言失败路径仍归还连接。
- 使用 **`get_db()`** 时，在 **`try` / `finally` 中对生成器调用 `close()`**（或等价的 `try`/`finally` 包裹），不要依赖「第二次 `next`」触发 `StopIteration` 来结束生成器；否则在第一次 `next` 之后、生成器未走完时若断言失败，可能延迟或不触发 `get_db` 内的 `db.close()`。

### 集成测试、行锁与死锁风险（审查要点）

**仓库现状（静态审查）**：`backend/tests` 内未发现多线程或 `pytest-xdist` 并行进程同时对真实库执行 `with_for_update` / `SELECT … FOR UPDATE` 的用例；`with_for_update` 仅出现在 `tests/game_engine/test_world_package_runtime.py` 对 **`WorldRuntimeRepository.get_state_for_update` 的 Mock 替身**中，不触发数据库行锁。标记为 `postgres_integration` 等的用例多为 **单 `Session`、短事务、`try/finally` 关闭**，与「长事务占满连接池」类问题相比，死锁风险较低。

**编写或扩展 PG 集成测试时须避免的模式**（易与生产侧长事务叠加表现为挂起或死锁）：

1. **多行锁顺序**：同一事务或协作的多连接若锁定多行，须按**稳定键**统一顺序（如主键、`world_id` 排序）；应用层参考 `WorldRuntimeRepository.get_state_for_update` 的 `order_by` 约定；测试中若手写 ORM 行锁，禁止依赖「自然顺序」。
2. **持锁等待**：避免在**未提交**的数据库事务内调用 `time.sleep`、同步网络 I/O 或等待另一测试线程；持锁区间应仅覆盖必要读写。
3. **并行与共享数据**：启用 **pytest-xdist**（`-n auto` 等）对**同一数据库实例**跑集成测试时，不得让多个 worker 争抢同一固定主键/同一业务行而不做隔离（唯一前缀、独立 schema 或禁用该标记下的 xdist）；否则表现为阻塞而非必然「死锁」，但症状类似。
4. **嵌套会话与事务边界**：多段 `with db_session_context()` 为独立事务；不要用第二个连接去「读第一个连接未提交」的数据并据此加锁，以免逻辑挂起。

**结论**：当前测试树在上述维度上风险可控；新增真实行锁或并发用例时，应走代码评审并按上表自检。

### 测试 Fixtures

共享 fixtures 定义在 `backend/tests/conftest.py`:

| Fixture | 说明 |
|---------|------|
| `mock_db_session` | 模拟 SQLAlchemy 数据库会话 |
| `mock_user_node` | 模拟用户节点 |
| `mock_user_node_with_world` | 模拟有世界恢复状态的用户节点 |
| `mock_admin_node` | 模拟管理员用户节点 |
| `mock_ssh_session` | 模拟 SSH 会话 |
| `mock_ssh_client` | 模拟 Paramiko SSH 客户端 |
| `sample_room` | 示例空间 fixture |
| `sample_character` | 示例角色 fixture |
| `sample_world` | 示例世界 fixture |
| `mock_command_context` | 模拟命令执行上下文 |
| `mock_game_handler` | 模拟游戏处理器 |
| `mock_entry_router` | 模拟入口路由器 |

### 前端 vitest 配置

```typescript
// frontend/vitest.config.ts
export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
    }
  }
})
```

## Test Naming Convention

```
后端: test_<module>_<feature>.py
     test_ssh_session.py
     test_entry_router.py
     test_campus_life_entry_state.py

前端: <Module>.spec.ts
     LoginPage.spec.ts
     AuthStore.spec.ts
```

## Test Markers

### 后端 pytest markers

```python
@pytest.mark.unit          # 单元测试 - 隔离的组件测试
@pytest.mark.integration   # 集成测试 - 需要数据库/服务
@pytest.mark.ssh           # SSH 模块测试
@pytest.mark.models        # 数据模型测试
@pytest.mark.commands      # 命令系统测试
@pytest.mark.game          # 游戏引擎测试
@pytest.mark.api           # API 端点测试
@pytest.mark.e2e           # 端到端测试 (future)
```

### 前端 vitest markers

```typescript
// 在 describe 中使用
describe('LoginPage', () => {
  it('should render login form', () => { ... })
})
```

## CI Integration

```yaml
# GitHub Actions
- name: Run backend tests
  run: |
    cd backend
    pytest --cov=app --cov-report=xml --cov-report=html

- name: Run frontend tests
  run: |
    cd frontend
    npm run test:coverage
```

## Test Execution

```bash
# 后端测试
cd backend
pytest                          # 运行所有测试
pytest -m unit                  # 仅运行单元测试
pytest -m integration           # 仅运行集成测试
pytest --cov=app                # 带覆盖率

# 前端测试
cd frontend
npm run test                    # 运行所有测试
npm run test:ui                 # UI 模式
npm run test:coverage           # 带覆盖率
```

## Coverage Targets

| 模块 | 目标覆盖率 |
|------|-----------|
| core | 80% |
| ssh | 75% |
| commands | 80% |
| models | 70% |
| game_engine | 75% |

## Open Questions

- [ ] 是否引入 Cypress E2E 测试？
- [ ] 是否使用 pytest-randomly 随机测试顺序？
- [ ] 是否为前端引入 Storybook 视觉测试？
