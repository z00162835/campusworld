#!/usr/bin/env python3
"""
SSH系统测试脚本
测试SSH服务器的各个模块功能
"""

import sys
import os
import time
import threading
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.ssh.config import get_ssh_config, reload_ssh_config
from app.ssh.session import SSHSession, SessionManager, SessionMonitor
from app.ssh.commands import SSHCommandRegistry, register_builtin_commands


def print_header(title):
    """打印测试标题"""
    print(f"\n{'='*60}")
    print(f"🧪 {title}")
    print(f"{'='*60}")


def print_section(title):
    """打印测试章节"""
    print(f"\n📋 {title}")
    print("-" * 40)


def print_result(test_name, success, details=""):
    """打印测试结果"""
    status = "✅ 通过" if success else "❌ 失败"
    print(f"  {status}: {test_name}")
    if details:
        print(f"     详情: {details}")


def test_ssh_config():
    """测试SSH配置模块"""
    print_header("SSH配置模块测试")
    
    try:
        # 获取配置
        config = get_ssh_config()
        print_result("配置加载", True, f"端口: {config.port}, 主机: {config.host}")
        
        # 验证配置
        is_valid = config.validate_config()
        print_result("配置验证", is_valid)
        
        # 获取配置摘要
        summary = config.get_config_summary()
        print_result("配置摘要生成", len(summary) > 0, f"长度: {len(summary)} 字符")
        
        # 测试配置重载
        reloaded_config = reload_ssh_config()
        print_result("配置重载", reloaded_config is not None)
        
        # 测试配置获取方法
        server_config = config.get_server_config()
        print_result("服务器配置获取", len(server_config) > 0, f"配置项: {len(server_config)}")
        
        auth_config = config.get_auth_config()
        print_result("认证配置获取", len(auth_config) > 0, f"配置项: {len(auth_config)}")
        
        security_config = config.get_security_config()
        print_result("安全配置获取", len(security_config) > 0, f"配置项: {len(security_config)}")
        
    except Exception as e:
        print_result("SSH配置测试", False, str(e))


def test_session_management():
    """测试会话管理模块"""
    print_header("会话管理模块测试")
    
    try:
        # 创建会话管理器
        session_manager = SessionManager()
        print_result("会话管理器创建", True)
        
        # 创建测试会话
        test_session = SSHSession(
            session_id="test_session_1",
            username="test_user",
            user_id=1,
            user_attrs={
                "roles": ["user"],
                "permissions": ["user.view"],
                "access_level": "normal"
            }
        )
        print_result("测试会话创建", True, f"会话ID: {test_session.session_id}")
        
        # 添加会话
        session_manager.add_session(test_session)
        print_result("会话添加", True, f"当前会话数: {session_manager.get_session_count()}")
        
        # 获取会话
        retrieved_session = session_manager.get_session("test_session_1")
        print_result("会话获取", retrieved_session is not None, f"用户名: {retrieved_session.username}")
        
        # 测试会话信息
        session_info = test_session.get_session_info()
        print_result("会话信息获取", len(session_info) > 0, f"信息项: {len(session_info)}")
        
        # 测试命令历史
        test_session.add_command("test_command")
        test_session.add_command("another_command")
        print_result("命令历史记录", len(test_session.command_history) == 2)
        
        # 测试会话统计
        stats = session_manager.get_session_stats()
        print_result("会话统计", len(stats) > 0, f"统计项: {len(stats)}")
        
        # 测试会话监控
        monitor = SessionMonitor(session_manager)
        summary = monitor.get_connection_summary()
        print_result("连接摘要", len(summary) > 0, f"摘要项: {len(summary)}")
        
        # 测试安全检查
        issues = monitor.check_security_issues()
        print_result("安全检查", isinstance(issues, list))
        
        # 测试报告生成
        report = monitor.generate_report()
        print_result("报告生成", len(report) > 0, f"报告长度: {len(report)}")
        
        # 清理测试会话
        session_manager.remove_session("test_session_1")
        print_result("会话清理", session_manager.get_session_count() == 0)
        
    except Exception as e:
        print_result("会话管理测试", False, str(e))


def test_command_system():
    """测试命令系统"""
    print_header("命令系统测试")
    
    try:
        # 创建命令注册表
        registry = SSHCommandRegistry()
        print_result("命令注册表创建", True)
        
        # 注册内置命令
        register_builtin_commands(registry)
        print_result("内置命令注册", len(registry.commands) > 0, f"命令数: {len(registry.commands)}")
        
        # 测试命令获取
        help_cmd = registry.get_command("help")
        print_result("帮助命令获取", help_cmd is not None, f"命令名: {help_cmd.name}")
        
        system_cmd = registry.get_command("system")
        print_result("系统命令获取", system_cmd is not None, f"命令名: {system_cmd.name}")
        
        # 测试命令列表
        all_commands = registry.get_all_commands()
        print_result("命令列表获取", len(all_commands) > 0, f"命令数: {len(all_commands)}")
        
        # 测试命令帮助
        help_text = help_cmd.get_help()
        print_result("命令帮助", len(help_text) > 0, f"帮助长度: {len(help_text)}")
        
        # 测试命令使用说明
        usage = help_cmd.get_usage()
        print_result("命令使用说明", len(usage) > 0, f"使用说明长度: {len(usage)}")
        
        # 测试特定命令
        version_cmd = registry.get_command("version")
        if version_cmd:
            print_result("版本命令", True, f"命令名: {version_cmd.name}")
        
        status_cmd = registry.get_command("status")
        if status_cmd:
            print_result("状态命令", True, f"命令名: {status_cmd.name}")
        
        # 测试命令注销
        registry.unregister_command("help")
        print_result("命令注销", "help" not in registry.commands)
        
    except Exception as e:
        print_result("命令系统测试", False, str(e))


def test_integration():
    """测试集成功能"""
    print_header("集成功能测试")
    
    try:
        # 测试配置和会话管理的集成
        config = get_ssh_config()
        session_manager = SessionManager()
        
        # 创建多个测试会话
        test_sessions = []
        for i in range(3):
            session = SSHSession(
                session_id=f"test_session_{i}",
                username=f"test_user_{i}",
                user_id=i,
                user_attrs={
                    "roles": ["user"],
                    "permissions": ["user.view"],
                    "access_level": "normal"
                }
            )
            session_manager.add_session(session)
            test_sessions.append(session)
        
        print_result("多会话创建", len(test_sessions) == 3)
        
        # 测试会话监控
        monitor = SessionMonitor(session_manager)
        summary = monitor.get_connection_summary()
        print_result("多会话监控", summary['active_sessions'] == 3)
        
        # 测试命令系统集成
        registry = SSHCommandRegistry()
        register_builtin_commands(registry)
        
        # 模拟命令执行环境
        class MockConsole:
            def __init__(self):
                self.command_registry = registry
                self.ssh_interface = type('MockSSHInterface', (), {
                    'session_manager': session_manager
                })()
            
            def get_session(self):
                return test_sessions[0] if test_sessions else None
        
        mock_console = MockConsole()
        
        # 测试命令执行
        help_cmd = registry.get_command("help")
        if help_cmd:
            try:
                result = help_cmd.execute(mock_console, [])
                print_result("命令执行测试", len(result) > 0, f"结果长度: {len(result)}")
            except Exception as e:
                print_result("命令执行测试", False, f"执行错误: {e}")
        
        # 清理测试数据
        for session in test_sessions:
            session_manager.remove_session(session.session_id)
        
        print_result("测试数据清理", session_manager.get_session_count() == 0)
        
    except Exception as e:
        print_result("集成功能测试", False, str(e))


def test_performance():
    """测试性能"""
    print_header("性能测试")
    
    try:
        # 测试会话创建性能
        session_manager = SessionManager()
        start_time = time.time()
        
        for i in range(100):
            session = SSHSession(
                session_id=f"perf_session_{i}",
                username=f"perf_user_{i}",
                user_id=i,
                user_attrs={
                    "roles": ["user"],
                    "permissions": ["user.view"],
                    "access_level": "normal"
                }
            )
            session_manager.add_session(session)
        
        create_time = time.time() - start_time
        print_result("批量会话创建", True, f"100个会话创建时间: {create_time:.3f}秒")
        
        # 测试命令注册性能
        registry = SSHCommandRegistry()
        start_time = time.time()
        register_builtin_commands(registry)
        register_time = time.time() - start_time
        print_result("命令注册性能", True, f"命令注册时间: {register_time:.3f}秒")
        
        # 测试会话查询性能
        start_time = time.time()
        for i in range(100):
            session_manager.get_session(f"perf_session_{i}")
        query_time = time.time() - start_time
        print_result("会话查询性能", True, f"100次查询时间: {query_time:.3f}秒")
        
        # 测试统计信息生成性能
        start_time = time.time()
        for i in range(10):
            stats = session_manager.get_session_stats()
        stats_time = time.time() - start_time
        print_result("统计信息生成性能", True, f"10次统计生成时间: {stats_time:.3f}秒")
        
        # 清理性能测试数据
        for i in range(100):
            session_manager.remove_session(f"perf_session_{i}")
        
        print_result("性能测试数据清理", session_manager.get_session_count() == 0)
        
    except Exception as e:
        print_result("性能测试", False, str(e))


def main():
    """主测试函数"""
    print("🚀 开始SSH系统测试")
    print("=" * 60)
    
    # 执行各项测试
    test_ssh_config()
    test_session_management()
    test_command_system()
    test_integration()
    test_performance()
    
    print("\n" + "=" * 60)
    print("🎉 SSH系统测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
