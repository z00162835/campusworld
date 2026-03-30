# Testing ACCEPTANCE - 验收检查表

## 测试配置验收

### pytest.ini 验证

- [x] `testpaths = tests` 正确指向测试目录
- [x] `python_files = test_*.py` 正确匹配测试文件
- [x] `asyncio_mode = auto` 已配置
- [x] markers 包含所有测试类型 (unit/integration/ssh/models/commands/game/api/e2e)

### conftest.py 验证

- [x] 包含 `mock_db_session` fixture
- [x] 包含 `mock_user_node` fixture
- [x] 包含 `mock_ssh_session` fixture
- [x] 包含 `sample_room` / `sample_character` / `sample_world` fixtures
- [x] 包含 `mock_command_context` fixture
- [x] 包含 `mock_game_handler` / `mock_entry_router` fixtures

## 测试文件验收

### 后端测试

- [x] `test_singularity_room.py` 迁移为 pytest class
- [x] `test_demo_building_generator.py` 迁移为 pytest
- [x] `test_database_compatibility.py` 迁移为 pytest + integration marker
- [x] integration 测试正确标记 `@pytest.mark.integration`
- [x] 24 个核心测试全部通过

### 前端测试

- [x] vitest.config.ts 包含 coverage 配置
- [x] setup.ts 包含基本 setup (vue-router, axios, element-plus mocks)
- [x] 至少有一个示例测试文件 (Login.spec.ts)

## 测试执行验收

### 后端

```bash
cd backend
pytest -v                              # 验证测试可运行 ✓
pytest -m unit                         # 验证 marker 过滤
pytest --cov=app --cov-report=xml      # 验证覆盖率
```

结果: 24 passed in 0.32s

### 前端

```bash
cd frontend
npm run test -- --run                  # 验证测试可运行 ✓
npm run test:coverage                  # 验证覆盖率
```

结果: 5 tests passed

## 测试规范验收

- [x] `docs/testing/SPEC/SPEC.md` 存在且完整
- [x] 测试分类清晰 (unit/integration/ssh/models/commands)
- [x] 命名约定统一 (test_*.py / *.spec.ts)
- [x] fixtures 文档完整 (conftest.py 说明)

## CI 集成验收

- [ ] GitHub Actions 包含 pytest 运行
- [ ] 覆盖率报告生成
- [ ] 测试结果可视化

## 测试覆盖目标

| 模块 | 当前覆盖率 | 目标覆盖率 |
|------|-----------|-----------|
| core | - | 80% |
| ssh | - | 75% |
| commands | - | 80% |
| models | - | 70% |
| game_engine | - | 75% |
