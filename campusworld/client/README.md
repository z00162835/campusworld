# CampusWorld CLI 客户端

CampusWorld CLI 客户端 `campus` 提供增强的终端交互体验，支持即时按键捕获、命令选择叠加层和 Tab 自动补全。

## 安装

```bash
cd client
pip install -e .
```

## 使用

```bash
# 基本连接
campus

# 指定服务器
campus --host localhost --port 8000

# 指定用户
campus --user test

# 指定配置文件
campus --config ./campus.yaml
```

## 配置

配置文件位于 `~/.config/campus/config.yaml` 或项目本地的 `campus.yaml`。

```yaml
server:
  host: "localhost"
  port: 8000
  use_ssl: false

auth:
  token_file: "~/.config/campus/token"

terminal:
  theme: "default"
  prompt_format: "[{user}@{time}] campusworld> "

completion:
  enabled: true
  show_on_slash: true
```

## 交互

- `/` - 显示命令选择列表
- `↑↓` - 在命令列表中选择
- `Enter` - 执行选中的命令
- `Tab` - 自动补全命令
- `ESC` - 取消当前操作

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
