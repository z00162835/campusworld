# CampusWorld CLI 客户端

CampusWorld CLI 客户端 `campus` 提供增强的终端交互体验，基于 Textual 框架构建，支持命令面板、模糊搜索和富文本输出。

背景与目标（Context & Goals）

### 1.1 问题陈述

本文说明CampusWorld的命令系统的设计理念、整体架构、命令的定义和分类以及具体命令的能力

### 1.2 目标

- **主要目标**：清晰描述命令系统的设计理念，整体架构，命令的定义与分类，并描述主要具体命令的能力
    
- **成功指标**：帮助开发者和AI Agent理解命令系统
    

### 1.3 非目标（Non-Goals）

不涉及对系统数据Model的设计与描述

## 2. 概念（Concept）

CampusWorld的命令系统设计目标是用户通过CLI端使用系统提供的命令完成交互，通过交互使用系统的全部能力，达成用户的业务目标，命令系统的相关概念定义如下：
命令系统：是一种智能的命令容器，本质是一个Agent容器，其负责管理系统提供的各类命令，包括：普通命令和智能命令，提供命令的整个生命周期管理能力；

命令分类：
从提供者分为系统命令和应用命令：
- 系统命令：CampusWorld系统（CampusOS）原生提供的系统命令，如：help/look/time/enter等
- 应用命令：由第三方应用提供的命令，如：第三方安全巡检Agent提供一个智能命令secagent

从能力分为普通命令和智能命令：
- 普通命令： 也称为工具命令，解决一类问题，提供的能力范围固定，如：look命令，help命令
- 智能命令:    也称为Agent命令，提供理解用户意图，具备可交互能力并能够解决领域问题的智能体环境，如：labagent命令，可进入labagent模式，与其交互，labagent提供一系列能力，包括lab看护，笔记生成等等

从使用角色分为管理员命令，操作员命令，开发者命令和用户命令：
- 管理员命令： 面向系统维护和控制者提供的一系列命令，如：world负责系统世界包的安装加载
- 操作员命令:    面向系统维护和设置者提供的一系列命令，如：call负责管理和配置各类agent
- 开发者命令： 面向系统开发者提供的一系列命令，如：dig可以构建世界的实例，比如：新增加一个room
- 用户命令:  面向用户提供的一系列命令，用于与系统提供的给类能力的交互，如：look用于观察用户所处的世界

3. 用户故事（User Stories）

采用标准格式：**作为 [角色]，我希望 [功能]，以便 [价值]**

| ID     | 用户故事                                                                       | 优先级 | 验收标准                                                                                  |
| ------ | -------------------------------------------------------------------------- | --- | ------------------------------------------------------------------------------------- |
| US-001 | 作为用户（管理员/操作员/开发者/用户）使用CLI（campus）或SSH Client登陆系统后，可使用命令系统与系统交互，使用系统提供的各类能力 | P0  | 各类用户登陆后可使用相应的命令，不同用户可见不同的命令，如：world命令只有管理员可见，look命令所有用户都可见                            |
| US-002 | 作为用户（管理员/操作员/开发者/用户）使用CLI（campus）登陆系统后可见欢迎页面，并出现系统提示符>                     | P0  | 各类用户执行campus命令，输入用户名和密码后登陆后可见欢迎页面，并出现系统提示符>                                           |
| US-003 | 作为用户（管理员/操作员/开发者/用户）使用CLI登陆系统后type /后可通过up或down按键选择系统对应提供的命令               | P0  | 各类用户登陆后type /后在提示行下部显示命令列表，可通过up或down按键选择用户可见的命令                                      |
| US-004 | 作为用户（管理员/操作员/开发者/用户）使用CLI登陆系统后type /后选择一个普通命令执行enter后可选择命令并执行命令            | P0  | 1、各类用户登陆后type /后在提示行下部显示命令列表，可通过up或down按键选择用户可见的命令<br>2、执行普通命令后，命令显示内容呈现在提示符以上的CLI空间中 |
| US-005 | 作为用户（管理员/操作员/开发者/用户）使用CLI登陆系统后type /后选择一个智能命令执行enter后可进入智能命令环境域进行交互互动      | P0  | 各类用户登陆后type /后在提示行下部显示命令列表，可通过up或down按键选择用户可见的命令                                      |

## 技术栈

- **Textual** - 现代 Python TUI 框架
- **WebSocket** - 与后端实时通信
- **asyncio** - 异步 I/O

## 安装

```bash
cd client
pip install -e .
```

## 快速开始

```bash
# 基本连接（使用默认配置或交互式输入）
campus

# 指定服务器和用户
campus --host localhost --port 8000 --user test

# 使用配置文件
campus --config ./campus.json
```

## 配置文件

### 配置位置

| 优先级 | 路径 | 说明 |
|--------|------|------|
| 1 | `./campus.json` | 项目本地配置 |
| 2 | `~/.config/campus/config.json` | 用户全局配置 |

### 完整配置项

```yaml
# campus.yaml - CampusWorld CLI 客户端配置

# 服务端连接配置
server:
  host: "localhost"        # 服务端地址
  port: 8000               # WebSocket 端口
  use_ssl: false           # 是否使用 SSL/TLS

# 认证配置
auth:
  token_file: "~/.config/campus/token"  # Token 文件路径
  default_user: "guest"    # 默认用户名

# 终端 UI 配置
terminal:
  theme: "default"         # 主题: default, dark
  font_size: 14           # 字体大小
  font_family: "monospace" # 字体

# 命令补全配置
completion:
  enabled: true            # 是否启用命令补全
  fuzzy_match: true        # 是否模糊匹配

# 命令历史配置
history:
  enabled: true
  size: 1000              # 历史记录条数
  file: "~/.local/share/campus/history"  # 历史文件路径

# 日志配置
logging:
  level: "info"           # 日志级别: debug, info, warning, error
  file: "~/.local/share/campus/logs/campus.log"
```

### 配置示例

```yaml
# 开发环境
server:
  host: "localhost"
  port: 8000

# 生产环境
server:
  host: "campus.example.com"
  port: 8443
  use_ssl: true
```

## 交互

### 快捷键

| 按键 | 功能 |
|------|------|
| `/` | 在提示符线下方显示命令列表 |
| `Tab` | 命令补全 |
| `↑↓` | 在命令列表中导航 |
| `Enter` | 执行/选中的命令 |
| `ESC` | 关闭命令列表/取消输入/退出 Agent 环境 |
| `Ctrl+C` | 退出程序 |

### 命令面板

按 `/` 打开命令列表：

```
┌──────────────────────────────────────┐
│ >/                         │
├──────────────────────────────────────┤
│  help     - 显示帮助                 │
│ ● look   - 查看当前环境      ← 选中  │
│  who     - 在线用户                  │
│  quit    - 退出系统                 │
└──────────────────────────────────────┘
```

功能：
- 输入文字进行实时模糊搜索
- 使用箭头键导航
- 按 Enter 执行选中命令

### 命令补全

在输入框输入命令前缀，按 `Tab` 键自动补全：

```
❯ lo<Tab>
可能的补全: login, logout, look
```

### 直接输入

也可以直接在底部输入框输入命令按 Enter 执行。

### Agent 环境

CampusWorld 支持 Agent 交互环境：

```
❯ /labagent
进入 labagent 环境
可用命令:
  ls      - 列出所有 agent 实例
  @<id>   - 进入指定的 agent 实例
  exit    - 退出 agent 环境

[labagent]❯ ls
labagent1  - CPU 分析 agent
labagent2  - 内存分析 agent

[labagent]❯ @labagent1
进入 agent 实例 labagent1
提示：此 agent 提供 check 命令可用

[labagent1]❯ check
正在执行 check...
结果: OK
```

## 功能特性

### 命令列表
- 内置模糊搜索
- 实时过滤命令
- 键盘导航

### Tab 命令补全
- 输入前缀自动补全
- 显示多个匹配选项

### Agent 环境
- 进入 Agent 环境 `/<agent>`
- 列出可用实例 `ls`
- 进入特定实例 `@<id>`
- 退出环境 `exit`

### 富文本输出
- 彩色日志输出
- 命令执行结果高亮
- 错误信息红色显示

### 连接管理
- WebSocket 实时通信
- 自动重连
- 会话状态保持

### 命令历史
- 上下箭头访问历史
- 持久化存储
- 搜索过滤

## 命令行参数

```bash
campus [options]
  --host <address>      服务端地址 (覆盖配置)
  --port <port>         服务端端口 (覆盖配置)
  --user <username>     用户名
  --config <path>       指定配置文件路径
  --debug               调试模式
```

## WebSocket API

客户端通过 WebSocket 连接到 `ws://localhost:8000/ws`。

### 消息格式

```json
// 连接
{"type": "connect", "user_id": "1", "username": "test"}

// 执行命令
{"type": "execute", "command": "look", "args": []}

// 请求补全
{"type": "complete", "partial": "lo"}

// 响应
{"type": "result", "success": true, "message": "..."}
```

## 目录结构

```
client/
├── campus/
│   ├── __init__.py
│   ├── __main__.py          # 入口
│   ├── config.py             # 配置加载
│   ├── connection.py         # WebSocket 连接
│   ├── protocol.py           # 协议处理
│   └── terminal.py           # Textual 终端
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 开发

```bash
# 安装开发依赖
pip install -e .

# 运行客户端
python -m campus

# 或安装后运行
campus
```

## 故障排除

### 连接失败
- 检查服务端是否运行：`curl http://localhost:8000/health`
- 验证端口配置是否正确
- 检查防火墙设置

### 命令无响应
- 按 `Ctrl+C` 取消当前输入
- 重启客户端

### 界面显示异常
- 尝试调整终端字体大小
- 确保终端支持 UTF-8 字符
