# Protocols - 协议处理

处理不同协议的请求，包括 HTTP 和 SSH。

## 模块结构

```
protocols/
├── __init__.py
├── base.py           # 协议基类
├── http_handler.py   # HTTP协议处理
└── ssh_handler.py    # SSH协议处理
```

## 核心概念

### ProtocolHandler (基类)

```python
class ProtocolHandler(ABC):
    @abstractmethod
    def handle(self, request):
        pass

    @abstractmethod
    def authenticate(self, credentials):
        pass

    @abstractmethod
    def send_response(self, response):
        pass
```

## HTTP 处理

### HTTPHandler

处理 FastAPI 请求:

```python
class HTTPHandler(ProtocolHandler):
    def __init__(self, app: FastAPI):
        self.app = app
        self.router = APIRouter()

    def setup_routes(self):
        # 设置API路由
        self.router.include_router(...)

    def handle(self, request: Request) -> Response:
        # 处理HTTP请求
        pass
```

### API 端点

REST API 通过 `app/api/v1/` 定义:

```
api/v1/
├── api.py           # API路由器
├── endpoints/
│   ├── auth.py     # 认证端点
│   └── accounts.py # 账户端点
└── schemas/
    ├── auth.py     # 认证schema
    └── account.py  # 账户schema
```

## SSH 处理

### SSHHandler

处理 SSH 会话命令:

```python
class SSHHandler(ProtocolHandler):
    def __init__(self, session: SSHSession):
        self.session = session

    def handle(self, command: str):
        # 解析和执行命令
        result = command_registry.execute(command, context, args)
        return result

    def authenticate(self, credentials):
        # SSH认证
        pass
```

## 使用方式

```python
from app.protocols.http_handler import HTTPHandler
from app.protocols.ssh_handler import SSHHandler

# HTTP处理
http_handler = HTTPHandler(app)
http_handler.setup_routes()

# SSH处理
def handle_ssh_command(session, command):
    handler = SSHHandler(session)
    return handler.handle(command)
```

## 协议对比

| 特性 | HTTP | SSH |
|------|------|-----|
| 用途 | Web API | 终端交互 |
| 认证 | JWT/Basic | 密码/公钥 |
| 状态 | 无状态 | 有状态 |
| 响应 | JSON | 文本流 |

## 扩展协议

可通过继承 `ProtocolHandler` 添加新协议:

```python
class WebSocketHandler(ProtocolHandler):
    def handle(self, websocket):
        # WebSocket处理
        pass
```
