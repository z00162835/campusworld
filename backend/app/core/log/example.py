"""
日志模块使用示例
演示如何使用日志模块的各种功能
"""
import time
from app.core.log import get_logger, setup_logging, log_function_call, log_execution_time, log_ssh_command, log_database_operation, create_logging_middleware, LoggerNames

def example_basic_logging():
    """基础日志使用示例"""
    print('=== 基础日志使用示例 ===')
    logger = get_logger('example.basic')
    logger.debug('Sample debug log')
    logger.info('Sample info log')
    logger.warning('Sample warning log')
    logger.error('Sample error log')
    logger.critical('Sample critical error log')

def example_decorators():
    """装饰器使用示例"""
    print('\n=== 装饰器使用示例 ===')
    logger = get_logger('example.decorators')

    @log_function_call(logger)
    def simple_function(x, y):
        """简单函数"""
        return x + y

    @log_execution_time(logger)
    def slow_function():
        """慢函数"""
        time.sleep(0.1)
        return '完成'
    result1 = simple_function(1, 2)
    result2 = slow_function()
    print(f'简单函数结果: {result1}')
    print(f'慢函数结果: {result2}')

def example_ssh_command():
    """SSH命令装饰器示例"""
    print('\n=== SSH命令装饰器示例 ===')

    class MockSSHCommand:

        def __init__(self, name):
            self.name = name
            self.current_session = MockSession()

        @log_ssh_command(get_logger('example.ssh'))
        def execute(self, console, args):
            """执行SSH命令"""
            return f'执行命令: {self.name} with args: {args}'

    class MockSession:

        def __init__(self):
            self.username = 'test_user'
    command = MockSSHCommand('help')
    result = command.execute(None, ['arg1', 'arg2'])
    print(f'SSH命令结果: {result}')

def example_database_operation():
    """数据库操作装饰器示例"""
    print('\n=== 数据库操作装饰器示例 ===')

    class MockDatabase:

        def __init__(self):
            self.logger = get_logger('example.database')

        @log_database_operation(get_logger('example.database'))
        def save(self, data):
            """保存数据"""
            return f'保存数据: {data}'

        @log_database_operation(get_logger('example.database'))
        def delete(self, id):
            """删除数据"""
            return f'删除数据: {id}'
    db = MockDatabase()
    result1 = db.save({'name': 'test', 'value': 123})
    result2 = db.delete(1)
    print(f'保存结果: {result1}')
    print(f'删除结果: {result2}')

def example_middleware():
    """中间件使用示例"""
    print('\n=== 中间件使用示例 ===')
    middleware = create_logging_middleware('example.middleware')
    middleware.log_request({'method': 'GET', 'path': '/api/test', 'user_id': '123'})
    middleware.log_response({'status': 200, 'data': {'result': 'success'}})
    middleware.log_performance('api_call', 0.5, {'endpoint': '/api/test'})
    middleware.log_error(Exception('测试错误'), {'context': '测试上下文'})

def example_custom_setup():
    """自定义日志设置示例"""
    print('\n=== 自定义日志设置示例 ===')
    setup_logging(level='DEBUG', format_str='%(asctime)s [%(levelname)s] %(name)s: %(message)s', file_path='logs/example.log', console_output=True, file_output=True)
    logger = get_logger('example.custom')
    logger.debug('Debug log from custom configuration')
    logger.info('Information log from custom configuration')

def example_module_loggers():
    """模块日志器示例"""
    print('\n=== 模块日志器示例 ===')
    app_logger = get_logger(LoggerNames.APP)
    ssh_logger = get_logger(LoggerNames.SSH)
    game_logger = get_logger(LoggerNames.GAME)
    database_logger = get_logger(LoggerNames.DATABASE)
    audit_logger = get_logger(LoggerNames.AUDIT)
    security_logger = get_logger(LoggerNames.SECURITY)
    app_logger.info('Application log message')
    ssh_logger.info('SSH log message')
    game_logger.info('World log message')
    database_logger.info('Database log message')
    audit_logger.info('Audit log message')
    security_logger.warning('Security log message')

def main():
    """主函数"""
    print('日志模块使用示例')
    print('=' * 50)
    example_basic_logging()
    example_decorators()
    example_ssh_command()
    example_database_operation()
    example_middleware()
    example_custom_setup()
    example_module_loggers()
    print('\n示例完成！')
if __name__ == '__main__':
    main()
