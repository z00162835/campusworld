# SSH Module - SSH终端服务

基于 Paramiko 实现的 SSH 服务器，提供类 MUD 游戏的多人交互终端。

## 架构设计（双层架构）

参考 Evenia 的 Portal-Server 双层架构设计：

```
┌─────────────────────────────────────────────────────────────┐
│                    CampusWorld SSH                          │
├─────────────────────────────────────────────────────────────┤
│  Protocol Layer (protocol_handler.py)                      │
│  - SSH 连接管理                                            │
│  - 用户认证                                                │
│  - 会话生命周期                                            │
│  - 通道管理                                                │
├─────────────────────────────────────────────────────────────┤
│  Game Layer (game_handler.py)                              │
│  - 用户认证验证                                            │
│  - 用户 spawn/位置管理                                      │
│  - 会话状态管理                                            │
│  - 游戏事件处理                                            │
├─────────────────────────────────────────────────────────────┤
│  server.py - 服务器生命周期管理                              │
│  session.py - 会话存储                                      │
│  console.py - 终端交互                                      │
└─────────────────────────────────────────────────────────────┘
```

## 模块组成

```
ssh/
├── server.py            # SSH服务器（生命周期管理）
├── protocol_handler.py  # Protocol Layer - SSH协议处理
├── game_handler.py     # Game Layer - 游戏逻辑处理
├── session.py          # 会话管理
├── console.py          # 终端控制台
└── input_handler.py    # 输入处理
```

### server.py - SSH服务器

**CampusWorldSSHServerInterface** (继承自 `SSHProtocolHandler`)
- 处理 SSH 连接认证（委托给 GameHandler）
- 管理多个 SSH 会话

**CampusWorldSSHServer**
- SSH 服务器主类
- 监听和接受连接
- 事件驱动架构

### protocol_handler.py - 协议层 (新增)

**SSHProtocolHandler** (继承自 `paramiko.ServerInterface`)
- SSH 协议处理
- 用户认证入口（委托给 GameHandler）
- 会话创建

**ProtocolFactory**
- 协议处理器工厂
- 主机密钥加载（4096位RSA）

### game_handler.py - 游戏层 (新增)

**GameHandler**
- `authenticate_user()`: 用户认证
- `spawn_user()`: 用户spawn到初始位置
- `get_user_location()`: 获取用户位置
- `update_user_activity()`: 更新用户活动

### session.py - 会话管理

**SSHSession**
- 单个 SSH 会话
- 输入/输出流管理
- 会话状态跟踪
- 命令历史

**SessionManager**
- 全局会话管理
- 会话注册/注销
- 广播消息

**SessionMonitor**
- 会话监控线程
- 心跳检测

### console.py - 终端控制台

**SSHConsole**
- 命令行界面渲染
- 命令解析和执行
- 输出格式化

### input_handler.py - 输入处理

**InputHandler**
- 行编辑支持
- 命令补全
- 历史记录导航

## 启动SSH服务器

```bash
cd backend

# 方式1: 直接运行
python -m app.ssh.server

# 方式2: 通过主程序
python campusworld.py --ssh-only

# 方式3: Docker环境
docker compose -f docker-compose.dev.yml up ssh
```

## 配置项

```yaml
ssh:
  enabled: true
  host: 0.0.0.0
  port: 2222
  host_key_path: ssh_host_key
  auth_timeout: 60
  banner: "Welcome to CampusWorld"
```

## 连接方式

```bash
# SSH客户端连接
ssh username@localhost -p 2222

# 使用密码认证
# 用户名和密码与Web账户相同
```

## 安全特性

- 支持密码认证
- 主机密钥验证（4096位RSA）
- 认证超时控制
- 会话隔离
- 输入验证
- 游戏逻辑与协议层分离，便于安全审计
