# CampusWorld 游戏引擎系统

## 概述

CampusWorld游戏引擎是一个参考Evennia框架设计的游戏与引擎解耦系统。它提供了完整的游戏基础设施，包括对象系统、命令系统、脚本系统、事件钩子系统等，同时保持了与现有SSH系统的完全兼容性。

## 设计理念

### 核心原则

1. **引擎与游戏分离**：引擎提供基础设施，游戏提供具体内容
2. **插件化架构**：游戏作为插件加载，不影响引擎核心
3. **共享数据库**：引擎和游戏共享数据存储
4. **保持SSH能力**：不改变现有SSH交互功能

### 参考Evennia框架

- **Typeclass系统**：对象类型系统
- **Command系统**：命令处理系统
- **Script系统**：脚本和定时任务
- **Hook系统**：事件钩子系统

## 系统架构

### 目录结构

```
campusworld/backend/
├── app/
│   ├── game_engine/           # 游戏引擎核心
│   │   ├── __init__.py        # 包初始化
│   │   ├── base.py            # 引擎基类
│   │   ├── loader.py          # 游戏加载器
│   │   ├── interface.py       # 游戏接口
│   │   └── manager.py         # 引擎管理器
│   ├── games/                 # 内置游戏
│   │   ├── __init__.py
│   │   └── campus_life/       # 校园生活游戏
│   │       ├── __init__.py
│   │       ├── game.py        # 游戏主类
│   │       ├── commands.py    # 游戏命令
│   │       ├── objects.py     # 游戏对象
│   │       └── scripts.py     # 游戏脚本
│   └── ssh/                   # SSH系统（保持不变）
├── config/
│   └── game_engine.yml        # 游戏引擎配置
├── start_game_engine.py       # 游戏引擎启动脚本
└── GAME_ENGINE_README.md      # 本文档
```

### 核心组件

#### 1. GameEngine (base.py)
- 游戏引擎基类
- 生命周期管理
- 核心系统管理（对象、命令、脚本、钩子）

#### 2. GameLoader (loader.py)
- 游戏模块发现和加载
- 热重载支持
- 依赖管理
- 版本兼容性检查

#### 3. GameInterface (interface.py)
- 游戏与引擎的交互接口
- 命令系统集成
- 对象系统访问
- 事件系统集成

#### 4. GameEngineManager (manager.py)
- 游戏引擎管理器（单例模式）
- 统一的游戏引擎管理接口
- 与SSH系统的集成

## 使用方法

### 1. 启动游戏引擎

```bash
cd campusworld/backend
python start_game_engine.py
```

### 2. SSH连接和交互

```bash
ssh -p 2222 campus@localhost
```

### 3. 游戏引擎管理命令

```bash
# 查看引擎状态
game status

# 列出所有游戏
game list

# 加载游戏
game load campus_life

# 卸载游戏
game unload campus_life

# 重新加载游戏
game reload campus_life

# 启动引擎
game start

# 停止引擎
game stop

# 查看帮助
game help
```

### 4. 游戏命令

```bash
# 查看游戏帮助
help

# 查看环境
look campus

# 移动到其他位置
move library

# 查看背包
inventory

# 查看角色状态
stats
```

## 开发新游戏

### 1. 创建游戏目录结构

```
games/your_game/
├── __init__.py
├── game.py
├── commands.py
├── objects.py
└── scripts.py
```

### 2. 实现游戏类

```python
from app.game_engine.base import BaseGame

class Game(BaseGame):
    def __init__(self):
        super().__init__("your_game", "1.0.0")
        self.description = "游戏描述"
        self.author = "作者名"
    
    def start(self) -> bool:
        # 实现启动逻辑
        pass
    
    def stop(self) -> bool:
        # 实现停止逻辑
        pass
    
    def get_commands(self) -> Dict[str, Any]:
        # 返回命令映射
        pass
```

### 3. 实现命令系统

```python
class YourGameCommands:
    def __init__(self, game):
        self.game = game
        self.command_handlers = {
            "command1": self._cmd_command1,
            "command2": self._cmd_command2,
        }
    
    def _cmd_command1(self, *args):
        return "命令1的执行结果"
```

### 4. 注册游戏

游戏引擎会自动发现和加载符合要求的游戏模块。

## 配置说明

### 游戏引擎配置 (config/game_engine.yml)

```yaml
game_engine:
  name: "CampusWorld"
  version: "1.0.0"
  max_games: 10
  auto_reload: true
  debug_mode: false
  log_level: "INFO"

game_loader:
  search_paths:
    - "app/games"
    - "games"
    - "../games"
  auto_load: true
  hot_reload: true
```

## 技术特性

### 1. 模块化设计
- 游戏作为独立模块加载
- 支持热重载
- 依赖管理

### 2. 事件驱动架构
- 事件钩子系统
- 异步事件处理
- 事件优先级管理

### 3. 对象系统
- 类型化对象管理
- 对象缓存
- 自动持久化

### 4. 命令系统
- 命令注册和管理
- 权限控制
- 命令别名

### 5. 脚本系统
- 定时任务
- 脚本执行
- 超时控制

## 扩展性

### 1. 新协议支持
- 可以添加HTTP、WebSocket等协议
- 协议与游戏逻辑分离

### 2. 新游戏类型
- 支持各种类型的游戏
- 统一的接口规范

### 3. 插件系统
- 支持第三方插件
- 插件生命周期管理

## 性能优化

### 1. 缓存策略
- 对象缓存
- 命令缓存
- LRU缓存策略

### 2. 资源管理
- 内存使用监控
- 自动资源清理
- 负载均衡

### 3. 异步处理
- 非阻塞I/O
- 事件队列
- 并发控制

## 安全特性

### 1. 权限系统
- 角色管理
- 权限检查
- 访问控制

### 2. 审计日志
- 操作记录
- 安全事件监控
- 日志分析

## 故障排除

### 1. 常见问题

#### 游戏加载失败
- 检查游戏目录结构
- 验证Python语法
- 查看错误日志

#### 命令不响应
- 检查命令注册
- 验证权限设置
- 查看SSH连接状态

#### 引擎启动失败
- 检查配置文件
- 验证依赖安装
- 查看系统日志

### 2. 调试模式

```yaml
game_engine:
  debug_mode: true
  log_level: "DEBUG"
```

### 3. 日志文件

- 游戏引擎日志：`logs/game_engine.log`
- SSH服务日志：`logs/ssh_server.log`

## 未来规划

### 1. 功能增强
- Web管理界面
- 游戏编辑器
- 性能监控面板

### 2. 协议扩展
- RESTful API
- GraphQL支持
- 实时通信

### 3. 游戏支持
- 3D游戏支持
- 多人游戏
- 游戏存档系统

## 贡献指南

### 1. 代码规范
- 遵循PEP 8
- 类型注解
- 文档字符串

### 2. 测试要求
- 单元测试
- 集成测试
- 性能测试

### 3. 提交规范
- 清晰的提交信息
- 功能分支
- 代码审查

## 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 联系方式

- 项目主页：https://github.com/your-org/campusworld
- 问题反馈：https://github.com/your-org/campusworld/issues
- 讨论区：https://github.com/your-org/campusworld/discussions

---

*本文档最后更新：2025年8月26日*
