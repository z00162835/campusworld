# SSH SPEC

> **Architecture Role**: SSH 模块是**系统适配层**的接入协议之一，提供类 MUD 终端的交互能力，是 Agent/用户进入**世界语义**的主要入口。用户通过 SSH 终端输入命令，命令系统操作知识本体，实现与世界语义的双向交互。

## Module Overview

SSH 服务器（`backend/app/ssh/`）基于 Paramiko 实现，采用 Evennia 的 Portal-Server 双层架构设计。

> **注**：CampusWorld 是智慧园区 OS，SSH 终端是用户与园区空间交互的标准接口之一，借鉴 MUD 设计原理而非开发游戏。

```
连接 → Protocol Layer → Game Layer → Security Layer → 命令执行
```

## 架构设计（四层架构）

```
┌─────────────────────────────────────────────────────────────┐
│  Protocol Layer (protocol_handler.py)                       │
│  - SSH 连接管理                                             │
│  - 用户认证入口                                             │
│  - 会话生命周期                                             │
│  - 通道管理                                                 │
├─────────────────────────────────────────────────────────────┤
│  Game Layer (game_handler.py)                               │
│  - 用户认证验证                                             │
│  - 用户 spawn/位置管理                                       │
│  - 会话状态管理                                             │
│  - 世界语义交互                                             │
├─────────────────────────────────────────────────────────────┤
│  Security Layer (rate_limiter.py)                           │
│  - 连接速率限制                                             │
│  - 登录失败追踪                                             │
│  - IP 锁定保护                                             │
├─────────────────────────────────────────────────────────────┤
│  Infrastructure (server.py/session.py/console.py)           │
│  - 服务器生命周期管理                                       │
│  - 会话存储与监控                                           │
│  - 终端渲染与输入处理                                       │
└─────────────────────────────────────────────────────────────┘
```

## Core Abstractions

### 核心类

| 类 | 文件 | 说明 |
|---|---|---|
| `CampusWorldSSHServer` | server.py | SSH 服务器主类，生命周期管理 |
| `CampusWorldSSHServerInterface` | server.py | Paramiko ServerInterface 实现 |
| `SSHProtocolHandler` | protocol_handler.py | SSH 协议处理 |
| `ProtocolFactory` | protocol_handler.py | 协议处理器工厂 |
| `GameHandler` | game_handler.py | 游戏层：authenticate_user/spawn_user |
| `SSHSession` | session.py | 单个 SSH 会话 |
| `SessionManager` | session.py | 全局会话管理 |
| `SessionMonitor` | session.py | 心跳检测 |
| `SSHConsole` | console.py | 终端交互渲染 |
| `InputHandler` | input_handler.py | 行编辑/命令补全/历史记录 |
| `ConnectionRateLimiter` | rate_limiter.py | 连接速率限制 |
| `LoginAttemptTracker` | rate_limiter.py | 登录失败追踪 |

### SSH 会话状态机

```
DISCONNECTED
    ↓ (连接建立)
AUTHENTICATING
    ↓ (认证成功)
AUTHENTICATED
    ↓ (spawn 到位置)
ACTIVE
    ↓ (命令输入)
COMMAND_EXECUTION → 返回结果 → ACTIVE
    ↓ (quit/disconnect)
DISCONNECTED
```

## User Stories

1. **连接园区**: 用户通过 SSH 客户端连接园区，输入用户名密码认证
2. **进入园区**: 认证成功后 spawn 到 SingularityRoom 或上次离开的位置
3. **命令交互**: 通过终端命令与园区空间交互（look/go/say 等）
4. **安全防护**: 连续登录失败 5 次后 IP 被锁定 5 分钟

## Acceptance Criteria

- [ ] `ssh username@localhost -p 2222` 能建立 SSH 连接
- [ ] 正确用户名密码登录成功，进入园区空间
- [ ] 错误密码连续 5 次后，IP 被锁定 300 秒
- [ ] `quit` 命令后正确断开 SSH 连接
- [ ] 同时支持 50 个并发 SSH 会话

## Design Decisions

1. **为何分层设计**: Protocol Layer 处理 SSH 协议，Game Layer 处理业务逻辑，Security Layer 处理安全防护，职责分离便于独立测试和扩展
2. **为何用 Event-Driven**: SSH 是长连接，会话状态变化需要即时响应，事件驱动模型天然适合
3. **为何速率限制**: 防止暴力破解和 DDoS，登录失败追踪防止凭证猜测

## Open Questions

- [ ] 是否需要公钥认证支持？
- [ ] 会话数据是否需要持久化（断线重连）？
- [ ] 是否需要命令执行超时机制？

## Dependencies

- 依赖 `backend/app/commands/`（命令执行）
- 依赖 `backend/app/models/`（用户/Character 实体）
- 依赖 `backend/app/core/security.py`（认证）
- 依赖 `backend/app/core/log/`（日志）