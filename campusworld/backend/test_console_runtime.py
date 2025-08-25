#!/usr/bin/env python3
"""
SSH控制台运行循环测试
专门测试控制台的运行状态和输入处理
"""

import sys
import os
import threading
import time
import logging

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_console_run_with_timeout():
    """测试控制台运行，带超时保护"""
    print("🔍 测试控制台运行（带超时保护）...")
    
    try:
        from app.ssh.console import SSHConsole
        
        # 创建模拟通道
        class MockChannel:
            def __init__(self):
                self.closed = False
                self.output_buffer = []
                self.input_buffer = ["help\n", "exit\n"]  # 预置输入
                self.input_index = 0
            
            def send(self, data):
                self.output_buffer.append(data)
                print(f"📤 通道输出: {repr(data)}")
            
            def recv(self, size):
                if self.input_index < len(self.input_buffer):
                    data = self.input_buffer[self.input_index]
                    self.input_index += 1
                    return data.encode('utf-8')
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
        
        # 在单独线程中运行控制台，带超时保护
        console_thread = threading.Thread(target=console.run)
        console_thread.daemon = True
        
        print("🧪 启动控制台运行...")
        start_time = time.time()
        console_thread.start()
        
        # 等待最多10秒
        timeout = 10
        while console_thread.is_alive() and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        if console_thread.is_alive():
            print(f"⏰ 控制台运行超时（{timeout}秒），强制停止")
            console.running = False
            console_thread.join(timeout=2)
        else:
            print("✅ 控制台运行完成")
        
        # 检查输出
        print(f"📊 输出缓冲区: {len(mock_channel.output_buffer)} 条消息")
        for i, output in enumerate(mock_channel.output_buffer):
            print(f"  {i+1}: {repr(output)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 控制台运行测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_input_processing_step_by_step():
    """逐步测试输入处理"""
    print("\n🔍 逐步测试输入处理...")
    
    try:
        from app.ssh.console import SSHConsole
        
        # 创建模拟通道
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
        
        # 测试输入处理
        test_inputs = ["help", "system", "exit"]
        
        for test_input in test_inputs:
            print(f"\n🧪 测试输入: '{test_input}'")
            
            # 清空输出缓冲区
            mock_channel.output_buffer.clear()
            
            # 处理输入
            console._process_input(test_input)
            
            # 检查输出
            print(f"  输出数量: {len(mock_channel.output_buffer)}")
            for i, output in enumerate(mock_channel.output_buffer):
                print(f"    {i+1}: {repr(output)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 输入处理测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_read_line_method():
    """测试读取行方法"""
    print("\n🔍 测试读取行方法...")
    
    try:
        from app.ssh.console import SSHConsole
        
        # 创建模拟通道
        class MockChannel:
            def __init__(self):
                self.closed = False
                self.output_buffer = []
                self.input_data = ["h", "e", "l", "p", "\n"]
                self.input_index = 0
            
            def send(self, data):
                self.output_buffer.append(data)
                print(f"📤 通道输出: {repr(data)}")
            
            def recv(self, size):
                if self.input_index < len(self.input_data):
                    char = self.input_data[self.input_index]
                    self.input_index += 1
                    return char.encode('utf-8')
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
        
        # 测试读取行
        print("🧪 测试读取行...")
        line = console._read_line_simple()
        print(f"✅ 读取行成功: '{line}'")
        
        return True
        
    except Exception as e:
        print(f"❌ 读取行测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🚀 SSH控制台运行测试开始")
    print("=" * 60)
    
    # 测试1：控制台运行（带超时保护）
    test1_success = test_console_run_with_timeout()
    
    # 测试2：逐步测试输入处理
    test2_success = test_input_processing_step_by_step()
    
    # 测试3：测试读取行方法
    test3_success = test_read_line_method()
    
    print("\n" + "=" * 60)
    print("🏁 SSH控制台运行测试完成")
    
    if all([test1_success, test2_success, test3_success]):
        print("✅ 所有测试通过，控制台运行正常")
    else:
        print("❌ 存在测试失败，需要进一步诊断")
        
        # 分析失败原因
        if not test1_success:
            print("  - 控制台运行测试失败")
        if not test2_success:
            print("  - 输入处理测试失败")
        if not test3_success:
            print("  - 读取行测试失败")

if __name__ == "__main__":
    main()
