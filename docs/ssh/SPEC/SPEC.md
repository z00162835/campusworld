# SSH SPEC

> **Architecture Role**: SSH 模块是**系统适配层**的接入协议之一，提供类 MUD 终端的交互能力，是 Agent/用户进入**世界语义**的主要入口。用户通过 SSH 终端输入命令，命令系统操作知识本体，实现与世界语义的双向交互。

## Module Overview

SSH 服务器（`backend/app/ssh/`）基于 Paramiko 实现，采用 Evennia 的 Portal-Server 双层架构设计。

### SPEC 管理约束（模块内）

- SSH 特性文档统一存放于 `docs/ssh/SPEC/features/`。
- `docs/ssh/SPEC/` 根目录仅保留模块级文件：`SPEC.md`、`TODO.md`、`ACCEPTANCE.md`。
- 公告栏特性规范唯一来源：`docs/ssh/SPEC/features/F00_BULLETIN_BOARD.md`。
- 会话生命周期（idle / teardown）：`docs/ssh/SPEC/features/F01_SSH_SESSION_LIFECYCLE.md`。

> **注**：CampusWorld 是智慧园区 OS，SSH 终端是用户与园区空间交互的标准接口之一，借鉴 MUD 设计原理而非开发。

```
连接 → Protocol Layer → Game Layer → Security Layer → 命令执行
```

## Unified Terms (Cross-SPEC)

- **System Entry Space**: `SingularityRoom`，系统级默认登录入口。
- **World Default Spawn**: 用户进入某个具体世界后，该世界内部的默认出生点（例如 `hicampus` 的 `hicampus_gate`）。
- **Last Location Resume**: 恢复用户上次有效位置的策略，不应与“系统入口”语义冲突。

## Login to Hub Call Chain (Current Implementation)

1. `CampusWorldSSHServer._handle_client()` creates a **per-connection** `SSHProtocolHandler` (Portal) with `client_ip` and shared `SessionManager`.
2. `SSHProtocolHandler.check_auth_password()` calls `game_handler.authenticate_user()`; enforces `max_sessions_per_user` when configured.
3. On success, `SSHSession` is registered in the shared `SessionManager`; handler holds `authenticated_session` for this transport only.
4. After `Transport.accept()`, server binds channel, calls `game_handler.spawn_user()`, then `touch_session(..., reason='console_ready')`.
5. `SSHConsole.run()` drives the interactive shell.

该调用链说明：Portal 粒度为每 TCP 连接一个 handler；Session 注册表与 idle/`who` 仍为进程级共享。同进程同步调用，不是进程间消息架构。

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
| `CampusWorldSSHServer` | server.py | SSH 服务器主类，生命周期管理；持有 `host_key` 与共享 `SessionManager` |
| `SSHProtocolHandler` | protocol_handler.py | 每连接 Portal：Paramiko ServerInterface，认证与 transport 上下文 |
| `ProtocolFactory` | protocol_handler.py | 协议处理器工厂 |
| `GameHandler` | game_handler.py | 层：authenticate_user/spawn_user |
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
2. **进入系统入口**: 认证成功后进入 `SingularityRoom`（或按恢复策略进入有效位置）
3. **命令交互**: 通过终端命令与园区空间交互（look/go/say 等）
4. **安全防护**: 连续登录失败 5 次后 IP 被锁定 5 分钟

## Post-Authentication Routing Policy

- **新用户**：认证成功后默认进入 `SingularityRoom`。
- **已有用户**：若启用恢复策略且上次位置有效，可进入 Last Location；否则回退 `SingularityRoom`。
- **目标世界不可达/无权限**：保持在 `SingularityRoom`，返回可选世界或失败原因，不中断会话。
- **边界约束**：SSH 层只负责认证与会话建立；“入口->世界”路由策略由业务策略层定义。

## Acceptance Criteria

- [ ] `ssh username@localhost -p 2222` 能建立 SSH 连接
- [ ] 正确用户名密码登录成功，进入 `SingularityRoom` 或策略允许的恢复位置
- [ ] 错误密码连续 5 次后，IP 被锁定 300 秒
- [ ] `quit` 命令后正确断开 SSH 连接
- [ ] 同时支持 50 个并发 SSH 会话
- [ ] 世界不可达/无权限时，用户保持在 `SingularityRoom` 并收到明确提示

## Design Decisions

1. **为何分层设计**: Protocol Layer 处理 SSH 协议，Game Layer 处理业务逻辑，Security Layer 处理安全防护，职责分离便于独立测试和扩展
2. **为何用 Event-Driven**: SSH 是长连接，会话状态变化需要即时响应，事件驱动模型天然适合
3. **为何速率限制**: 防止暴力破解和 DDoS，登录失败追踪防止凭证猜测

## Open Questions

- [ ] 是否需要公钥认证支持？
- [ ] 会话数据是否需要持久化（断线重连）？
- [ ] 是否需要命令执行超时机制？ → 见 F01（idle）与 TODO「命令执行超时」
- [ ] 是否将当前同进程调用升级为进程间消息交互（Portal/Server 分离）？

## Dependencies

- 依赖 `backend/app/commands/`（命令执行）
- 依赖 `backend/app/models/`（用户/Character 实体）
- 依赖 `backend/app/core/security.py`（认证）
- 依赖 `backend/app/core/log/`（日志）