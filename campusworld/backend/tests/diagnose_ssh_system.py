#!/usr/bin/env python3
"""
SSH系统诊断脚本
深度检查命令系统、权限检查、输出流等
"""

import sys
import os
import logging

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_command_registry():
    """测试命令注册表"""
    print("🔍 测试命令注册表...")
    
    try:
        from app.ssh.commands import SSHCommandRegistry, register_builtin_commands
        
        # 创建注册表
        registry = SSHCommandRegistry()
        print(f"✅ 命令注册表创建成功")
        
        # 注册命令
        register_builtin_commands(registry)
        print(f"✅ 内置命令注册完成")
        
        # 检查命令数量
        commands = registry.get_all_commands()
        print(f"📊 注册的命令数量: {len(commands)}")
        
        # 列出所有命令
        print("\n📋 已注册的命令:")
        for cmd in commands:
            print(f"  - {cmd.name}: {cmd.description}")
        
        # 检查help命令
        help_cmd = registry.get_command("help")
        if help_cmd:
            print(f"✅ help命令存在: {help_cmd.name}")
        else:
            print("❌ help命令不存在")
        
        # 检查别名
        aliases = registry.get_aliases()
        print(f"📊 别名数量: {len(aliases)}")
        for alias, command in aliases.items():
            print(f"  - {alias} -> {command}")
            
        return registry
        
    except Exception as e:
        print(f"❌ 命令注册表测试失败: {e}")
        return None

def test_command_execution(registry):
    """测试命令执行"""
    print("\n🔍 测试命令执行...")
    
    if not registry:
        print("❌ 注册表不存在，跳过命令执行测试")
        return
    
    try:
        # 获取help命令
        help_cmd = registry.get_command("help")
        if not help_cmd:
            print("❌ help命令不存在")
            return
        
        # 模拟控制台对象
        class MockConsole:
            def __init__(self, registry):
                self.command_registry = registry
                self.current_session = None
            
            def get_session(self):
                return self.current_session
        
        mock_console = MockConsole(registry)
        
        # 测试help命令执行
        print("🧪 测试help命令执行...")
        result = help_cmd.execute(mock_console, [])
        print(f"✅ help命令执行成功")
        print(f"📝 输出长度: {len(result)}")
        print(f"📄 输出内容:\n{result}")
        
    except Exception as e:
        print(f"❌ 命令执行测试失败: {e}")

def test_permission_system():
    """测试权限系统"""
    print("\n🔍 测试权限系统...")
    
    try:
        from app.core.permissions import permission_checker
        
        print("✅ 权限检查器导入成功")
        
        # 测试基本权限检查
        roles = ["user"]
        permission = "system.view"
        
        result = permission_checker.check_permission(roles, permission)
        print(f"📊 权限检查结果: {result}")
        
    except Exception as e:
        print(f"❌ 权限系统测试失败: {e}")

def test_ssh_console_creation():
    """测试SSH控制台创建"""
    print("\n🔍 测试SSH控制台创建...")
    
    try:
        from app.ssh.console import SSHConsole
        
        print("✅ SSH控制台类导入成功")
        
        # 创建模拟通道
        class MockChannel:
            def __init__(self):
                self.closed = False
                self.output = []
            
            def send(self, data):
                self.output.append(data)
            
            def recv(self, size):
                return b''
            
            def settimeout(self, timeout):
                pass
        
        mock_channel = MockChannel()
        
        # 创建模拟SSH接口
        class MockSSHInterface:
            def __init__(self):
                pass
        
        mock_interface = MockSSHInterface()
        
        # 创建控制台
        console = SSHConsole(mock_channel, mock_interface)
        print("✅ SSH控制台创建成功")
        
        # 检查命令注册表
        if console.command_registry:
            commands = console.command_registry.get_all_commands()
            print(f"📊 控制台中的命令数量: {len(commands)}")
        else:
            print("❌ 控制台中没有命令注册表")
        
        return console
        
    except Exception as e:
        print(f"❌ SSH控制台创建测试失败: {e}")
        return None

def main():
    """主函数"""
    print("🚀 SSH系统深度诊断开始")
    print("=" * 60)
    
    # 测试1：命令注册表
    registry = test_command_registry()
    
    # 测试2：命令执行
    test_command_execution(registry)
    
    # 测试3：权限系统
    test_permission_system()
    
    # 测试4：SSH控制台创建
    console = test_ssh_console_creation()
    
    print("\n" + "=" * 60)
    print("🏁 SSH系统深度诊断完成")
    
    if registry and console:
        print("✅ 所有核心组件测试通过")
    else:
        print("❌ 存在核心组件问题，需要进一步修复")

if __name__ == "__main__":
    main()
