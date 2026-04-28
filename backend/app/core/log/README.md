# 日志模块使用指南

这是一个功能完整、性能优化的Python日志模块，专为CampusWorld项目设计。

## 功能特性

- **统一日志管理**: 提供统一的日志接口和配置管理
- **多种装饰器**: 支持函数调用、执行时间、SSH命令、数据库操作等日志记录
- **结构化日志**: 支持JSON格式和结构化日志输出
- **日志中间件**: 提供请求、响应、错误、性能等结构化日志记录
- **多种格式化器**: 支持彩色控制台、JSON、审计等格式化器
- **灵活过滤器**: 支持敏感数据过滤、重复日志过滤、模块过滤等
- **上下文管理**: 支持日志上下文信息管理
- **配置管理**: 支持YAML/JSON配置文件管理

## 快速开始

### 1. 基础使用

```python
from app.core.logging import get_logger

# 获取日志器
logger = get_logger("my_module")
logger.info("这是一条日志消息")
```

### 2. 使用装饰器

```python
from app.core.logging import get_logger, log_function_call, log_execution_time

logger = get_logger("my_module")

@log_function_call(logger)
def my_function():
    return "结果"

@log_execution_time(logger)
def slow_function():
    time.sleep(0.1)
    return "完成"
```

### 3. 使用中间件

```python
from app.core.logging import create_logging_middleware

middleware = create_logging_middleware("my_module")
middleware.log_request({"method": "GET", "path": "/api/test"})
middleware.log_response({"status": 200, "data": {"result": "success"}})
```

### 4. 自定义配置

```python
from app.core.logging import setup_logging

setup_logging(
    level="DEBUG",
    format_str="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    file_path="logs/my_app.log",
    console_output=True,
    file_output=True
)
```

## 模块结构

```
app/core/logging/
├── __init__.py          # 模块入口
├── manager.py           # 日志管理器
├── decorators.py        # 日志装饰器
├── middleware.py        # 日志中间件
├── formatters.py        # 日志格式化器
├── handlers.py          # 日志处理器
├── filters.py           # 日志过滤器
├── context.py           # 日志上下文
├── config.py            # 日志配置
├── example.py           # 使用示例
└── README.md            # 使用指南
```

## 详细使用说明

### 日志管理器 (LoggingManager)

日志管理器是核心组件，负责统一管理日志配置和日志器创建。

```python
from app.core.logging import get_logging_manager

manager = get_logging_manager()
logger = manager.get_logger("my_module")
```

### 装饰器

#### 函数调用装饰器

```python
@log_function_call(logger)
def my_function(x, y):
    return x + y
```

#### 执行时间装饰器

```python
@log_execution_time(logger)
def slow_function():
    time.sleep(0.1)
    return "完成"
```

#### SSH命令装饰器

```python
class SSHCommand:
    @log_ssh_command(logger)
    def execute(self, console, args):
        return "命令执行结果"
```

#### 数据库操作装饰器

```python
class Database:
    @log_database_operation(logger)
    def save(self, data):
        return "保存成功"
```

### 中间件

日志中间件提供结构化的日志记录功能。

```python
middleware = create_logging_middleware("my_module")

# 记录请求
middleware.log_request({
    "method": "GET",
    "path": "/api/test",
    "user_id": "123"
})

# 记录响应
middleware.log_response({
    "status": 200,
    "data": {"result": "success"}
})

# 记录性能
middleware.log_performance("api_call", 0.5, {"endpoint": "/api/test"})

# 记录错误
middleware.log_error(Exception("测试错误"), {"context": "测试上下文"})
```

### 格式化器

#### JSON格式化器

```python
from app.core.logging.formatters import JSONFormatter

formatter = JSONFormatter()
handler.setFormatter(formatter)
```

#### 彩色格式化器

```python
from app.core.logging.formatters import ColoredFormatter

formatter = ColoredFormatter(use_colors=True)
handler.setFormatter(formatter)
```

#### 审计格式化器

```python
from app.core.logging.formatters import AuditFormatter

formatter = AuditFormatter()
handler.setFormatter(formatter)
```

### 过滤器

#### 敏感数据过滤器

```python
from app.core.logging.filters import SensitiveDataFilter

filter_instance = SensitiveDataFilter()
logger.addFilter(filter_instance)
```

#### 重复日志过滤器

```python
from app.core.logging.filters import DuplicateFilter

filter_instance = DuplicateFilter(max_duplicates=5, timeout=60.0)
logger.addFilter(filter_instance)
```

### 上下文管理

```python
from app.core.logging.context import get_logging_context, set_logging_context

# 设置上下文
set_logging_context(user_id="123", session_id="abc")

# 获取上下文
context = get_logging_context()
print(context)  # {'user_id': '123', 'session_id': 'abc'}
```

### 配置管理

```python
from app.core.logging.config import LoggingConfigManager

# 创建配置管理器
config_manager = LoggingConfigManager("config/logging.yaml")

# 加载配置
config = config_manager.load_config()

# 验证配置
errors = config_manager.validate_config()
if errors:
    print(f"配置错误: {errors}")
```

## 配置文件示例

### YAML配置

```yaml
# config/logging.yaml
level: "INFO"
format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
date_format: "%Y-%m-%d %H:%M:%S"

console_output: true
console_level: "INFO"
console_colored: true

file_output: true
file_path: "logs/campusworld.log"
file_level: "INFO"
file_max_size: "10MB"
file_backup_count: 5

module_levels:
  paramiko: "WARNING"
  asyncio: "WARNING"
  app.ssh: "INFO"
  app.games: "DEBUG"

filters:
  hide_passwords: true
  hide_tokens: true
  max_duplicates: 5
  duplicate_timeout: 60.0
```

## 性能优化

1. **延迟初始化**: 日志器采用延迟初始化，避免不必要的资源消耗
2. **缓存机制**: 日志器实例被缓存，避免重复创建
3. **异步处理**: 支持异步日志处理（需要额外配置）
4. **内存优化**: 使用内存处理器避免大量日志文件I/O

## 最佳实践

1. **使用预定义日志器**: 使用`LoggerNames`中预定义的日志器名称
2. **合理设置日志级别**: 生产环境使用INFO，开发环境使用DEBUG
3. **使用装饰器**: 对于需要记录的函数，使用相应的装饰器
4. **结构化日志**: 使用中间件记录结构化的日志信息
5. **敏感数据过滤**: 使用过滤器保护敏感信息
6. **日志轮转**: 配置合适的日志轮转策略

## 示例代码

运行示例代码：

```bash
python app/core/logging/example.py
```

这将演示日志模块的各种功能和使用方法。

## 注意事项

1. 确保日志目录存在且有写权限
2. 生产环境建议关闭DEBUG级别日志
3. 定期清理旧日志文件
4. 监控日志文件大小，避免磁盘空间不足
5. 敏感信息要使用过滤器进行脱敏处理
