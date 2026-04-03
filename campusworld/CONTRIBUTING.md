# 贡献指南

感谢您对 CampusWorld 项目的关注！我们欢迎所有形式的贡献，包括但不限于代码贡献、文档改进、问题报告和功能建议。

## 🤝 如何贡献

### 1. 报告问题 (Issues)

如果您发现了 bug 或有功能建议，请通过 GitHub Issues 报告：

- **Bug 报告**: 请使用 `bug` 标签，并详细描述问题
- **功能请求**: 请使用 `enhancement` 标签，说明新功能的用途
- **文档问题**: 请使用 `documentation` 标签
- **安全问题**: 请使用 `security` 标签，并私下联系维护者

### 2. 代码贡献

#### 准备工作

1. Fork 项目到您的 GitHub 账户
2. Clone 您的 fork 到本地：
   ```bash
   git clone https://github.com/your-username/campusworld.git
   cd campusworld
   ```
3. 添加上游仓库：
   ```bash
   git remote add upstream https://github.com/original-org/campusworld.git
   ```

#### 开发流程

1. 创建功能分支：
   ```bash
   git checkout -b feature/your-feature-name
   # 或者修复 bug
   git checkout -b fix/your-bug-fix
   ```

2. 进行开发并提交代码：
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```

3. 推送到您的 fork：
   ```bash
   git push origin feature/your-feature-name
   ```

4. 创建 Pull Request

#### 代码规范

##### Python 后端

- 使用 **Black** 进行代码格式化
- 使用 **isort** 进行导入排序
- 使用 **flake8** 进行代码检查
- 使用 **mypy** 进行类型检查
- 遵循 **PEP 8** 编码规范

```bash
# 格式化代码
black app tests
isort app tests

# 检查代码质量
flake8 app tests
mypy app
```

##### Vue 前端

- 使用 **ESLint** 进行代码检查
- 使用 **Prettier** 进行代码格式化
- 遵循 **Vue 3 Composition API** 最佳实践
- 使用 **TypeScript** 进行类型检查

```bash
# 检查代码质量
npm run lint

# 格式化代码
npm run format

# 类型检查
npm run type-check
```

#### 提交信息规范

我们使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

类型说明：
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建过程或辅助工具的变动

示例：
```
feat(auth): add JWT token authentication
fix(api): resolve user registration validation issue
docs(readme): update installation instructions
```

### 3. 文档贡献

文档是项目的重要组成部分，我们欢迎：

- 改进现有文档
- 添加新的使用示例
- 翻译文档到其他语言
- 修复文档中的错误

### 4. 测试贡献

- 为新功能添加测试用例
- 改进现有测试覆盖率
- 修复失败的测试
- 添加性能测试

## 🧪 开发环境设置

### 后端开发

```bash
cd backend

# 创建 conda 环境
conda env create -f environment.yml
conda activate campusworld

# 安装依赖
pip install -r requirements/dev.txt

# 运行测试
pytest

# 启动系统（主程序）
python campusworld.py
```

### 前端开发

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 运行测试
npm run test

# 构建生产版本
npm run build
```

### 使用 Docker

```bash
# 启动开发环境
docker-compose -f docker-compose.dev.yml up -d

# 启动生产环境
docker-compose up -d
```

## 📋 Pull Request 检查清单

在提交 Pull Request 之前，请确保：

- [ ] 代码遵循项目编码规范
- [ ] 添加了必要的测试用例
- [ ] 所有测试都通过
- [ ] 更新了相关文档
- [ ] 提交信息符合规范
- [ ] 没有引入新的警告或错误
- [ ] 代码已经过自我审查

## 🔍 代码审查

所有代码贡献都需要经过代码审查：

1. 至少需要一名维护者批准
2. 所有 CI 检查必须通过
3. 代码审查意见必须得到解决
4. 维护者保留最终决定权

## 📚 学习资源

如果您是新手，以下资源可能对您有帮助：

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Vue 3 官方文档](https://vuejs.org/)
- [Python 编码规范 (PEP 8)](https://www.python.org/dev/peps/pep-0008/)
- [Git 工作流](https://guides.github.com/introduction/flow/)

## 🏷️ 标签说明

我们使用以下标签来组织 Issues 和 PR：

- `good first issue`: 适合新手的简单问题
- `help wanted`: 需要帮助的问题
- `bug`: 需要修复的问题
- `enhancement`: 功能改进建议
- `documentation`: 文档相关
- `testing`: 测试相关
- `security`: 安全问题

## 📞 获取帮助

如果您在贡献过程中遇到问题：

1. 查看项目文档
2. 搜索现有的 Issues 和 PR
3. 在 GitHub Discussions 中提问
4. 联系项目维护者

## 🙏 致谢

感谢所有为 CampusWorld 项目做出贡献的开发者！您的贡献让这个项目变得更好。

---

**注意**: 通过贡献代码，您同意您的贡献将在项目的 MIT 许可证下发布。
