#!/usr/bin/env python3
"""
SSH输出格式测试脚本
测试命令执行后的输出格式是否正确居左对齐
"""

import subprocess
import time
import sys

def test_ssh_commands():
    """测试SSH命令输出格式"""
    print("🔍 开始测试SSH命令输出格式...")
    
    # 测试命令列表
    test_commands = [
        "system",      # 系统信息
        "user",        # 用户信息
        "who",         # 在线用户
        "status",      # 系统状态
        "help",        # 帮助信息
        "alias",       # 别名管理
        "version",     # 版本信息
        "date",        # 日期时间
    ]
    
    print(f"📋 将测试 {len(test_commands)} 个命令的输出格式")
    print("=" * 60)
    
    for i, cmd in enumerate(test_commands, 1):
        print(f"\n🔧 测试 {i}/{len(test_commands)}: {cmd}")
        print("-" * 40)
        
        try:
            # 执行SSH命令
            result = subprocess.run([
                "ssh", "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-p", "2222", "campus@localhost"
            ], input=f"{cmd}\nexit\n", text=True, capture_output=True, timeout=30)
            
            if result.returncode == 0:
                print("✅ 命令执行成功")
                # 分析输出格式
                analyze_output_format(cmd, result.stdout)
            else:
                print(f"❌ 命令执行失败: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            print("⏰ 命令执行超时")
        except Exception as e:
            print(f"💥 执行异常: {e}")
        
        print("-" * 40)
        time.sleep(1)  # 避免过快执行
    
    print("\n🎯 SSH输出格式测试完成！")

def analyze_output_format(command, output):
    """分析输出格式，检查第一行是否居左对齐"""
    if not output:
        print("⚠️  无输出内容")
        return
    
    lines = output.strip().split('\n')
    if not lines:
        print("⚠️  输出为空")
        return
    
    # 查找命令输出部分
    command_output_started = False
    output_lines = []
    
    for line in lines:
        if command in line and "campusworld>" in line:
            command_output_started = True
            continue
        
        if command_output_started and "campusworld>" in line:
            break
            
        if command_output_started:
            output_lines.append(line)
    
    if not output_lines:
        print("⚠️  未找到命令输出")
        return
    
    print(f"📊 输出行数: {len(output_lines)}")
    
    # 检查第一行格式
    first_line = output_lines[0].strip()
    if first_line:
        print(f"📝 第一行内容: '{first_line}'")
        
        # 检查是否居左对齐
        if first_line and first_line[0].isspace():
            print("❌ 格式问题: 第一行包含前导空格，未居左对齐")
            print(f"   前导字符: '{repr(first_line[:10])}'")
        else:
            print("✅ 格式正确: 第一行居左对齐")
    else:
        print("⚠️  第一行为空")
    
    # 显示前几行输出
    print("📋 输出预览:")
    for i, line in enumerate(output_lines[:5]):
        prefix = "  " if i == 0 else "   "
        print(f"{prefix}{i+1}: {repr(line)}")

if __name__ == "__main__":
    try:
        test_ssh_commands()
    except KeyboardInterrupt:
        print("\n⏹️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 测试执行异常: {e}")
        sys.exit(1)
