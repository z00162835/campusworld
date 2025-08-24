# Conda 环境设置指南

本指南介绍如何在 CampusWorld 项目中使用 Miniconda 管理 Python 环境。

## 🐍 为什么选择 Conda？

相比传统的 `venv` 虚拟环境，Conda 提供了以下优势：

- **跨平台兼容性**: 在 Windows、macOS 和 Linux 上表现一致
- **包管理**: 不仅管理 Python 包，还管理系统级依赖
- **环境隔离**: 更好的环境隔离和依赖管理
- **科学计算**: 对科学计算包有更好的支持
- **版本管理**: 可以管理多个 Python 版本

## 📥 安装 Miniconda

### 1. 下载安装

访问 [Miniconda 官网](https://docs.conda.io/en/latest/miniconda.html) 下载适合您系统的安装包：

- **Windows**: 下载 `.exe` 安装包
- **macOS**: 下载 `.pkg` 安装包或 `.sh` 脚本
- **Linux**: 下载 `.sh` 脚本

### 2. 安装步骤

#### Windows
```bash
# 运行下载的 .exe 文件
# 按照安装向导完成安装
# 建议选择"为所有用户安装"和"添加到 PATH"
```

#### macOS/Linux
```bash
# 下载安装脚本
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh

# 运行安装脚本
bash Miniconda3-latest-Linux-x86_64.sh

# 按照提示完成安装
# 建议选择"yes"添加到 PATH
```

### 3. 验证安装

安装完成后，重新打开终端并验证：

```bash
conda --version
```

## 🔧 配置 Conda

### 1. 初始化 Conda

首次使用需要初始化：

```bash
conda init
```

这会修改您的 shell 配置文件（如 `.bashrc`、`.zshrc`），添加 conda 初始化代码。

### 2. 配置镜像源（可选，国内用户推荐）

为了提高下载速度，可以配置国内镜像源：

```bash
# 添加清华镜像源
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge/

# 设置搜索时显示通道地址
conda config --set show_channel_urls yes
```

## 🚀 在 CampusWorld 中使用 Conda

### 1. 自动创建环境（推荐）

使用项目提供的初始化脚本：

```bash
./scripts/setup.sh
```

这个脚本会自动：
- 检查 conda 是否安装
- 创建 `campusworld` 环境
- 安装所有必要的依赖

### 2. 手动创建环境

如果您想手动控制环境创建过程：

```bash
cd backend

# 从环境文件创建环境
conda env create -f environment.yml

# 激活环境
conda activate campusworld

# 安装开发依赖
pip install -r requirements/dev.txt
```

### 3. 环境文件说明

项目提供了 `environment.yml` 文件，包含：

```yaml
name: campusworld          # 环境名称
channels:                  # 包源
  - conda-forge           # 社区维护的包
  - defaults               # 官方包
dependencies:              # 依赖列表
  - python=3.11           # Python 版本
  - pip                   # pip 包管理器
  - pip:                  # 通过 pip 安装的包
    - fastapi==0.104.1    # Web 框架
    - uvicorn[standard]   # ASGI 服务器
    # ... 其他依赖
```

## 🔄 环境管理命令

### 1. 环境操作

```bash
# 列出所有环境
conda env list

# 激活环境
conda activate campusworld

# 停用环境
conda deactivate

# 删除环境
conda env remove -n campusworld

# 克隆环境
conda create -n campusworld-clone --clone campusworld
```

### 2. 包管理

```bash
# 安装包
conda install package_name

# 通过 pip 安装包
pip install package_name

# 更新包
conda update package_name

# 删除包
conda remove package_name

# 列出已安装的包
conda list
```

### 3. 环境导出和导入

```bash
# 导出环境配置
conda env export > environment.yml

# 从配置文件创建环境
conda env create -f environment.yml

# 更新现有环境
conda env update -f environment.yml
```

## 🛠️ 开发工作流

### 1. 日常开发

```bash
# 进入项目目录
cd campusworld/backend

# 激活环境
conda activate campusworld

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 安装新依赖

```bash
# 激活环境
conda activate campusworld

# 安装新包
pip install new_package

# 更新环境文件
pip freeze > requirements/new_requirements.txt
```

### 3. 运行测试

```bash
# 激活环境
conda activate campusworld

# 运行测试
pytest

# 运行特定测试
pytest tests/test_auth.py

# 生成覆盖率报告
pytest --cov=app --cov-report=html
```

## 🔍 故障排除

### 1. 环境激活失败

```bash
# 重新初始化 conda
conda init

# 重新打开终端
# 或者手动初始化
source ~/miniconda3/etc/profile.d/conda.sh
```

### 2. 包安装失败

```bash
# 清理缓存
conda clean --all

# 更新 conda
conda update conda

# 尝试不同的安装方式
conda install package_name
# 或者
pip install package_name
```

### 3. 环境损坏

```bash
# 删除损坏的环境
conda env remove -n campusworld

# 重新创建环境
conda env create -f environment.yml
```

## 📚 最佳实践

### 1. 环境命名

- 使用描述性的环境名称
- 避免使用特殊字符
- 考虑添加版本号（如 `campusworld-v1.0`）

### 2. 依赖管理

- 定期更新 `environment.yml` 文件
- 指定包的版本号以确保一致性
- 分离开发和生产依赖

### 3. 环境隔离

- 为不同项目创建独立环境
- 避免在 base 环境中安装项目依赖
- 定期清理不再使用的环境

### 4. 版本控制

- 将 `environment.yml` 纳入版本控制
- 记录环境变更的原因和时间
- 在团队中共享环境配置

## 🔗 相关资源

- [Conda 官方文档](https://docs.conda.io/)
- [Miniconda 安装指南](https://docs.conda.io/en/latest/miniconda.html)
- [Conda 环境管理](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html)
- [Conda 包管理](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-pkgs.html)

---

通过使用 Conda 管理 Python 环境，您可以更好地控制项目依赖，确保开发环境的一致性和可重现性。
