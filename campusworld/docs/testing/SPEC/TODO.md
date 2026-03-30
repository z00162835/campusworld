# TODO - 测试工程开发任务

## 验收追踪

- 统一验收文档：`docs/testing/SPEC/ACCEPTANCE.md`
- pytest.ini 和 conftest.py 已创建
- standalone 测试已迁移为标准 pytest

## 测试文件迁移

### 已完成

- [x] 创建 `backend/pytest.ini`
- [x] 创建 `backend/tests/conftest.py`
- [x] 迁移 `test_singularity_room.py` → pytest class
- [x] 迁移 `test_demo_building_generator.py` → pytest
- [x] 迁移 `test_database_compatibility.py` → pytest + integration marker
- [x] 24 个核心测试全部通过

## 前端测试脚手架

### 已完成

- [x] 补充 `frontend/src/test/setup.ts` (mocks for vue-router, axios, element-plus)
- [x] 创建示例测试 `frontend/src/views/auth/Login.spec.ts`
- [x] 前端测试运行成功 (5 tests passed)

### 待完成

- [ ] 配置 vitest 覆盖率
- [ ] 创建 store 测试
- [ ] 创建更多组件测试
- [ ] 创建 API 测试

## 测试规范文档

### 已完成

- [x] 创建 `docs/testing/SPEC/SPEC.md`
- [x] 创建 `docs/testing/SPEC/TODO.md` (本文件)
- [x] 创建 `docs/testing/SPEC/ACCEPTANCE.md`

## CLAUDE.md 更新

### 已完成

- [x] 更新 `root CLAUDE.md` — 添加 Testing 小节
- [x] 更新 `backend/CLAUDE.md` — pytest.ini / conftest 说明
- [x] 更新 `frontend/CLAUDE.md` — vitest 说明
- [x] 更新 `backend/app/core/CLAUDE.md` — fixtures 说明

## 验收检查清单

- [x] `pytest` 在 backend/ 目录下无报错 (24 tests passed)
- [x] `npm run test` 在 frontend/ 目录下无报错 (5 tests passed)
- [x] 测试框架配置完整
- [x] 所有 CLAUDE.md 包含测试相关内容
- [x] `docs/testing/SPEC/SPEC.md` 完整覆盖测试规范

## 下一步

1. 配置 vitest 覆盖率报告
2. 添加更多前端测试 (store, components, API)
3. 完善 CI 集成
