#!/usr/bin/env python3
"""
SSH控制台功能测试脚本
测试命令执行、输入处理等功能
"""

import time
import subprocess
import sys

def test_ssh_connection():
    """测试SSH连接和基本功能"""
    print("🧪 测试SSH控制台功能...")
    
    # 测试1：基本连接
    print("\n1️⃣ 测试基本SSH连接...")
    try:
        result = subprocess.run([
            'ssh', '-p', '2222', 
            '-o', 'StrictHostKeyChecking=no', 
            '-o', 'UserKnownHostsFile=/dev/null',
            'campus@localhost'
        ], input=b'campus123\n', capture_output=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ SSH连接成功")
        else:
            print(f"❌ SSH连接失败: {result.stderr.decode()}")
            
    except subprocess.TimeoutExpired:
        print("⏰ SSH连接超时")
    except Exception as e:
        print(f"❌ SSH连接异常: {e}")
    
    # 测试2：命令执行
    print("\n2️⃣ 测试命令执行...")
    try:
        result = subprocess.run([
            'ssh', '-p', '2222', 
            '-o', 'StrictHostKeyChecking=no', 
            '-o', 'UserKnownHostsFile=/dev/null',
            'campus@localhost', 'help'
        ], input=b'campus123\n', capture_output=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ 命令执行成功")
            print(f"输出: {result.stdout.decode()[:100]}...")
        else:
            print(f"❌ 命令执行失败: {result.stderr.decode()}")
            
    except subprocess.TimeoutExpired:
        print("⏰ 命令执行超时")
    except Exception as e:
        print(f"❌ 命令执行异常: {e}")
    
    # 测试3：交互式会话
    print("\n3️⃣ 测试交互式会话...")
    try:
        # 启动SSH进程
        process = subprocess.Popen([
            'ssh', '-p', '2222', 
            '-o', 'StrictHostKeyChecking=no', 
            '-o', 'UserKnownHostsFile=/dev/null',
            'campus@localhost'
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 等待连接建立
        time.sleep(2)
        
        # 发送密码
        process.stdin.write(b'campus123\n')
        process.stdin.flush()
        
        # 等待认证
        time.sleep(2)
        
        # 发送help命令
        process.stdin.write(b'help\n')
        process.stdin.flush()
        
        # 等待响应
        time.sleep(2)
        
        # 发送exit命令
        process.stdin.write(b'exit\n')
        process.stdin.flush()
        
        # 等待进程结束
        try:
            stdout, stderr = process.communicate(timeout=5)
            print("✅ 交互式会话测试完成")
            if stdout:
                print(f"输出: {stdout.decode()[:200]}...")
        except subprocess.TimeoutExpired:
            process.kill()
            print("⏰ 交互式会话超时")
            
    except Exception as e:
        print(f"❌ 交互式会话异常: {e}")

def main():
    """主函数"""
    print("🚀 SSH控制台功能测试开始")
    print("=" * 50)
    
    test_ssh_connection()
    
    print("\n" + "=" * 50)
    print("🏁 SSH控制台功能测试完成")

if __name__ == "__main__":
    main()
