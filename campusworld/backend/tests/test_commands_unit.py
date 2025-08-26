#!/usr/bin/env python3
"""
命令系统单元测试
不依赖SSH连接，直接测试命令执行逻辑
"""

import sys
import os
import logging

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_help_command_directly():
    """直接测试help命令，不依赖控制台"""
    print("🔍 直接测试help命令...")
    
    try:
        from app.ssh.commands import SSHHelpCommand, SSHCommandRegistry
        
        # 创建命令注册表
        registry = SSHCommandRegistry()
        
        # 创建help命令
        help_cmd = SSHHelpCommand()
        print(f"✅ help命令创建成功: {help_cmd.name}")
        
        # 创建模拟控制台，提供command_registry
        class MockConsole:
            def __init__(self, registry):
                self.command_registry = registry
                self.current_session = None
            
            def get_session(self):
                return self.current_session
        
        mock_console = MockConsole(registry)
        
        # 直接执行命令
        print("🧪 执行help命令...")
        result = help_cmd.execute(mock_console, [])
        
        print(f"✅ 命令执行成功")
        print(f"📝 结果长度: {len(result) if result else 0}")
        print(f"📄 执行结果:\n{result}")
        
        return True
        
    except Exception as e:
        print(f"❌ help命令测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_command_registry_isolated():
    """隔离测试命令注册表"""
    print("\n🔍 隔离测试命令注册表...")
    
    try:
        from app.ssh.commands import SSHCommandRegistry, SSHHelpCommand, SSHSystemInfoCommand
        
        # 创建注册表
        registry = SSHCommandRegistry()
        print("✅ 命令注册表创建成功")
        
        # 注册命令
        help_cmd = SSHHelpCommand()
        system_cmd = SSHSystemInfoCommand()
        
        registry.register_command(help_cmd)
        registry.register_command(system_cmd)
        print("✅ 命令注册成功")
        
        # 测试命令查找
        help_found = registry.get_command("help")
        system_found = registry.get_command("system")
        
        if help_found and system_found:
            print("✅ 命令查找成功")
            print(f"  - help: {help_found.name}")
            print(f"  - system: {system_found.name}")
        else:
            print("❌ 命令查找失败")
            return False
        
        # 测试命令执行
        print("\n🧪 测试命令执行...")
        
        class MockConsole:
            def __init__(self):
                self.command_registry = registry
                self.current_session = None
            
            def get_session(self):
                return self.current_session
        
        mock_console = MockConsole()
        
        # 执行help命令
        help_result = help_cmd.execute(mock_console, [])
        print(f"✅ help命令执行成功，结果长度: {len(help_result) if help_result else 0}")
        
        # 执行system命令
        system_result = system_cmd.execute(mock_console, [])
        print(f"✅ system命令执行成功，结果长度: {len(system_result) if system_result else 0}")
        
        return True
        
    except Exception as e:
        print(f"❌ 命令注册表测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_console_methods_isolated():
    """隔离测试控制台方法"""
    print("\n🔍 隔离测试控制台方法...")
    
    try:
        from app.ssh.console import SSHConsole
        
        print("✅ SSH控制台类导入成功")
        
        # 创建模拟通道
        class MockChannel:
            def __init__(self):
                self.closed = False
                self.output_buffer = []
                self.input_buffer = []
            
            def send(self, data):
                self.output_buffer.append(data)
                print(f"📤 通道输出: {repr(data)}")
            
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
        
        # 创建控制台（不运行）
        console = SSHConsole(mock_channel, mock_interface)
        print("✅ SSH控制台创建成功")
        
        # 测试命令解析方法
        print("\n🧪 测试命令解析...")
        test_inputs = ["help", "system", "help system", "help --verbose"]
        
        for test_input in test_inputs:
            parts = console._parse_command(test_input)
            print(f"  输入: '{test_input}' -> 解析: {parts}")
        
        # 测试权限检查方法
        print("\n🧪 测试权限检查...")
        help_cmd = console.command_registry.get_command("help")
        if help_cmd:
            permission_result = console._check_command_permission(help_cmd, [])
            print(f"  help命令权限检查结果: {permission_result}")
        
        return True
        
    except Exception as e:
        print(f"❌ 控制台方法测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_command_execution_step_by_step():
    """逐步测试命令执行流程"""
    print("\n🔍 逐步测试命令执行流程...")
    
    try:
        from app.ssh.console import SSHConsole
        from app.ssh.commands import SSHCommandRegistry, SSHHelpCommand
        
        # 创建最小化测试环境
        registry = SSHCommandRegistry()
        help_cmd = SSHHelpCommand()
        registry.register_command(help_cmd)
        
        class MockChannel:
            def __init__(self):
                self.closed = False
                self.output_buffer = []
            
            def send(self, data):
                self.output_buffer.append(data)
                print(f"📤 通道输出: {repr(data)}")
            
            def recv(self, size):
                return b''
            
            def settimeout(self, timeout):
                pass
        
        mock_channel = MockChannel()
        
        class MockSSHInterface:
            def __init__(self):
                pass
        
        mock_interface = MockSSHInterface()
        
        # 创建控制台
        console = SSHConsole(mock_channel, mock_interface)
        
        # 步骤1：测试命令查找
        print("📋 步骤1：测试命令查找")
        command = console.command_registry.get_command("help")
        if not command:
            print("❌ 命令查找失败")
            return False
        print(f"✅ 命令查找成功: {command.name}")
        
        # 步骤2：测试权限检查
        print("📋 步骤2：测试权限检查")
        permission_result = console._check_command_permission(command, [])
        print(f"✅ 权限检查结果: {permission_result}")
        
        # 步骤3：测试命令执行
        print("📋 步骤3：测试命令执行")
        try:
            result = command.execute(console, [])
            print(f"✅ 命令执行成功，结果长度: {len(result) if result else 0}")
        except Exception as e:
            print(f"❌ 命令执行失败: {e}")
            return False
        
        # 步骤4：测试输出发送
        print("📋 步骤4：测试输出发送")
        if result:
            console._execute_command("help", [])
            print(f"✅ 输出发送完成，缓冲区: {len(mock_channel.output_buffer)} 条消息")
        
        return True
        
    except Exception as e:
        print(f"❌ 逐步测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🚀 命令系统单元测试开始")
    print("=" * 60)
    
    # 测试1：直接测试help命令
    test1_success = test_help_command_directly()
    
    # 测试2：隔离测试命令注册表
    test2_success = test_command_registry_isolated()
    
    # 测试3：隔离测试控制台方法
    test3_success = test_console_methods_isolated()
    
    # 测试4：逐步测试命令执行流程
    test4_success = test_command_execution_step_by_step()
    
    print("\n" + "=" * 60)
    print("🏁 命令系统单元测试完成")
    
    if all([test1_success, test2_success, test3_success, test4_success]):
        print("✅ 所有测试通过，命令系统正常")
    else:
        print("❌ 存在测试失败，需要进一步诊断")
        
        # 分析失败原因
        if not test1_success:
            print("  - help命令直接执行失败")
        if not test2_success:
            print("  - 命令注册表测试失败")
        if not test3_success:
            print("  - 控制台方法测试失败")
        if not test4_success:
            print("  - 命令执行流程测试失败")

if __name__ == "__main__":
    main()
