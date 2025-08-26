#!/usr/bin/env python3
"""
命令执行测试脚本
深度诊断SSH命令执行问题
"""

import sys
import os
import logging

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_basic_command_execution():
    """测试基本命令执行"""
    print("🔍 测试基本命令执行...")
    
    try:
        from app.ssh.commands import SSHCommandRegistry, SSHHelpCommand
        
        # 创建注册表
        registry = SSHCommandRegistry()
        print("✅ 命令注册表创建成功")
        
        # 创建help命令
        help_cmd = SSHHelpCommand()
        registry.register_command(help_cmd)
        print("✅ help命令注册成功")
        
        # 测试命令查找
        cmd = registry.get_command("help")
        if cmd:
            print(f"✅ help命令查找成功: {cmd.name}")
        else:
            print("❌ help命令查找失败")
            return False
        
        # 测试命令执行
        print("🧪 测试help命令执行...")
        
        # 模拟控制台对象
        class MockConsole:
            def __init__(self):
                self.command_registry = registry
                self.current_session = None
                self.output_buffer = []
            
            def get_session(self):
                return self.current_session
            
            def send_output(self, message):
                self.output_buffer.append(message)
                print(f"📤 输出: {message}")
        
        mock_console = MockConsole()
        
        # 执行命令
        result = help_cmd.execute(mock_console, [])
        print(f"✅ 命令执行完成，结果长度: {len(result) if result else 0}")
        print(f"📄 执行结果:\n{result}")
        
        return True
        
    except Exception as e:
        print(f"❌ 基本命令执行测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ssh_console_integration():
    """测试SSH控制台集成"""
    print("\n🔍 测试SSH控制台集成...")
    
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
        
        # 创建控制台
        console = SSHConsole(mock_channel, mock_interface)
        print("✅ SSH控制台创建成功")
        
        # 检查命令注册表
        if console.command_registry:
            commands = console.command_registry.get_all_commands()
            print(f"📊 控制台中的命令数量: {len(commands)}")
            
            # 查找help命令
            help_cmd = console.command_registry.get_command("help")
            if help_cmd:
                print(f"✅ help命令在控制台中可用: {help_cmd.name}")
            else:
                print("❌ help命令在控制台中不可用")
        else:
            print("❌ 控制台中没有命令注册表")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ SSH控制台集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_command_execution_flow():
    """测试命令执行流程"""
    print("\n🔍 测试命令执行流程...")
    
    try:
        from app.ssh.console import SSHConsole
        from app.ssh.commands import SSHCommandRegistry, SSHHelpCommand
        
        # 创建完整的测试环境
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
        
        mock_channel = MockChannel()
        
        class MockSSHInterface:
            def __init__(self):
                pass
        
        mock_interface = MockSSHInterface()
        
        # 创建控制台
        console = SSHConsole(mock_channel, mock_interface)
        
        # 手动执行help命令
        print("🧪 手动执行help命令...")
        
        # 模拟输入处理
        line = "help"
        print(f"📥 输入: {line}")
        
        # 解析命令
        command_parts = console._parse_command(line)
        print(f"🔍 解析结果: {command_parts}")
        
        if command_parts:
            command_name = command_parts[0]
            args = command_parts[1:]
            
            print(f"📋 命令名: {command_name}, 参数: {args}")
            
            # 执行命令
            console._execute_command(command_name, args)
            
            print(f"📊 输出缓冲区: {len(mock_channel.output_buffer)} 条消息")
            for i, output in enumerate(mock_channel.output_buffer):
                print(f"  {i+1}: {repr(output)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 命令执行流程测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🚀 SSH命令执行深度诊断开始")
    print("=" * 60)
    
    # 测试1：基本命令执行
    test1_success = test_basic_command_execution()
    
    # 测试2：SSH控制台集成
    test2_success = test_ssh_console_integration()
    
    # 测试3：命令执行流程
    test3_success = test_command_execution_flow()
    
    print("\n" + "=" * 60)
    print("🏁 SSH命令执行深度诊断完成")
    
    if test1_success and test2_success and test3_success:
        print("✅ 所有测试通过，命令执行系统正常")
    else:
        print("❌ 存在测试失败，需要进一步诊断")

if __name__ == "__main__":
    main()
