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

本地执行后端 `pytest` 时，应使用与项目依赖一致的 Python 环境。若使用 Conda 且已创建环境 **`campusworld`**，推荐在运行测试前执行：

```bash
conda activate campusworld
cd backend
pytest
```

避免默认 shell 指向 Conda **base** 或其它环境，导致缺少 `pytest`、依赖版本与 `requirements` 不一致等问题。无需持久激活时，可在 `backend` 目录下单次执行：

```bash
conda run -n campusworld pytest
```

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
