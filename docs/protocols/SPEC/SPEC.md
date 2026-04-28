# Protocols SPEC

> **Architecture Role**: 本模块是**系统适配层**的协议抽象层，统一 HTTP（FastAPI/REST）和 SSH（Paramiko/终端）两种接入方式。所有外部请求通过协议层进入系统，协议层将请求路由到命令系统，命令系统操作知识本体。

## Module Overview

协议处理（`backend/app/protocols/`）提供统一的协议抽象，支持多种接入方式。

```
外部请求
    ↓
ProtocolHandler (抽象基类)
    ├── HTTPHandler  → FastAPI
    └── SSHHandler   → Paramiko SSH
    ↓
命令系统 (commands/)
    ↓
知识本体 (models/)
```

## Core Abstractions

### ProtocolHandler 抽象基类

```python
class ProtocolHandler(ABC):
    @abstractmethod
    def handle(self, request): ...

    @abstractmethod
    def authenticate(self, credentials): ...

    @abstractmethod
    def send_response(self, response): ...
```

### HTTPHandler

- 集成 FastAPI Router
- 处理 REST API 请求
- 返回 JSON 响应

### SSHHandler

- 处理 SSH 会话命令
- 调用命令注册表
- 返回文本输出

## User Stories

1. **HTTP 接入**: 前端通过 Axios 发送 REST 请求，HTTPHandler 路由到对应端点
2. **SSH 接入**: 终端用户输入命令，SSHHandler 解析命令并调用命令系统
3. **协议扩展**: 新增 WebSocketHandler 只需继承 ProtocolHandler

## Acceptance Criteria

- [ ] HTTPHandler 能处理 FastAPI 请求并返回 JSON
- [ ] SSHHandler 能解析 SSH 会话中的命令并返回文本
- [ ] 新协议可通过继承 ProtocolHandler 添加

## Design Decisions

1. **为何协议抽象**: HTTP 和 SSH 是不同的接入方式，但都调用相同的命令系统，抽象层使协议切换无感知
2. **为何统一接口**: handle/authenticate/send_response 三步标准化所有协议的处理流程

## Open Questions

- [ ] WebSocket 协议是否需要实现？
- [ ] 协议层是否需要连接池管理？

## Dependencies

- 依赖 `backend/app/commands/`（命令执行）
- 依赖 `backend/app/api/v1/`（FastAPI 路由）