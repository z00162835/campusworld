# CampusWorld CLI 客户端

CampusWorld CLI 客户端 `campus` 提供增强的终端交互体验，基于 Textual 框架构建，支持命令面板、模糊搜索和富文本输出。

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
campus --config ./campus.yaml
```

## 配置文件

### 配置位置

| 优先级 | 路径 | 说明 |
|--------|------|------|
| 1 | `./campus.yaml` | 项目本地配置 |
| 2 | `~/.config/campus/config.yaml` | 用户全局配置 |

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
| `Ctrl+P` | 显示命令面板 |
| `Tab` | 命令补全 |
| `↑↓` | 在命令列表中导航 |
| `Enter` | 执行选中的命令 |
| `ESC` | 关闭命令面板/取消输入/退出 Agent 环境 |
| `Ctrl+C` | 退出程序 |

### 命令面板

按 `Ctrl+P` 打开命令面板：

```
┌──────────────────────────────────────┐
│ 🔍 命令面板                         │
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

### 命令面板
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
