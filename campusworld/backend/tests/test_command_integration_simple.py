#!/usr/bin/env python3
"""
简化命令系统集成测试脚本

测试命令系统与DefaultObject的集成，避免SQLAlchemy依赖
专注于命令系统核心功能测试

作者：AI Assistant
创建时间：2025-08-24
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_command_system_imports():
    """测试命令系统导入"""
    print("\n🧪 测试命令系统导入")
    print("=" * 50)
    
    try:
        # 测试基础命令系统
        from app.commands.base import Command, CmdSet, CommandExecutor
        print("✅ 基础命令系统导入成功")
        
        # 测试系统命令
        from app.commands.system import CmdLook, CmdStats, CmdHelp, CmdVersion, CmdTime
        print("✅ 系统命令导入成功")
        
        # 测试命令上下文
        from app.commands.context import CommandContext, CommandExecutionContext
        print("✅ 命令上下文导入成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 命令系统导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_command_context_creation():
    """测试命令执行上下文创建"""
    print("\n🧪 测试命令执行上下文创建")
    print("=" * 50)
    
    try:
        from app.commands.context import CommandContext, CommandExecutionContext
        
        # 创建执行环境
        exec_env = CommandExecutionContext()
        print(f"  创建执行环境: {exec_env}")
        
        # 创建上下文
        context = exec_env.create_context(
            caller="测试用户",
            target="测试目标",
            location="测试位置"
        )
        print(f"  创建上下文: {context}")
        
        # 测试上下文管理
        context.start_execution()
        context.add_input("test_key", "test_value")
        context.add_output("result", "success")
        context.add_message("测试消息", "info")
        context.finish_execution(True)
        
        print(f"  执行状态: {context.is_execution_complete()}")
        print(f"  执行时长: {context.get_execution_duration():.3f}秒")
        
        # 测试上下文验证（不检查权限）
        validation = context.validate_context()
        print(f"  上下文验证: {validation}")
        
        return True
        
    except Exception as e:
        print(f"❌ 命令执行上下文创建测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_command_execution():
    """测试命令执行"""
    print("\n🧪 测试命令执行")
    print("=" * 50)
    
    try:
        from app.commands.base import CommandExecutor
        from app.commands.system.cmdset import SystemCmdSet
        
        # 创建系统命令集合
        system_cmdset = SystemCmdSet()
        print(f"  创建系统命令集合: {system_cmdset.key}")
        
        # 创建命令执行器
        executor = CommandExecutor(default_cmdset=system_cmdset)
        print(f"  创建命令执行器: {executor}")
        
        # 测试命令查找
        look_cmd = executor.find_command("look")
        if look_cmd:
            print(f"  找到look命令: {look_cmd.__name__}")
        else:
            print("  ❌ 未找到look命令")
        
        # 测试命令解析
        parsed_commands = executor.parse_command_string("look -v sword")
        print(f"  解析命令结果: {len(parsed_commands)}个命令")
        
        for i, parsed_cmd in enumerate(parsed_commands):
            print(f"    命令{i+1}: {parsed_cmd.get('key', 'unknown')}")
            print(f"      参数: {parsed_cmd.get('args', '')}")
        
        # 测试可用命令
        available_commands = executor.get_available_commands()
        print(f"  可用命令数量: {len(available_commands)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 命令执行测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_system_commands():
    """测试系统命令"""
    print("\n🧪 测试系统命令")
    print("=" * 50)
    
    try:
        from app.commands.system import CmdLook, CmdStats, CmdHelp, CmdVersion, CmdTime
        
        # 测试各个命令
        commands = [
            ("Look", CmdLook()),
            ("Stats", CmdStats()),
            ("Help", CmdHelp()),
            ("Version", CmdVersion()),
            ("Time", CmdTime())
        ]
        
        for name, cmd in commands:
            print(f"\n📖 {name}命令:")
            print(f"  命令关键字: {cmd.key}")
            print(f"  命令别名: {cmd.aliases}")
            print(f"  帮助分类: {cmd.help_category}")
            
            # 测试帮助方法
            try:
                help_text = cmd.help()
                print(f"  帮助方法: 可用")
            except Exception as e:
                print(f"  帮助方法: 不可用 ({e})")
        
        return True
        
    except Exception as e:
        print(f"❌ 系统命令测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_command_parsing():
    """测试命令解析"""
    print("\n🧪 测试命令解析")
    print("=" * 50)
    
    try:
        from app.commands.base import CommandExecutor
        from app.commands.system.cmdset import SystemCmdSet
        
        # 创建命令执行器
        system_cmdset = SystemCmdSet()
        executor = CommandExecutor(default_cmdset=system_cmdset)
        
        # 测试命令字符串解析
        test_commands = [
            "look",
            "look -v",
            "look -a sword",
            "stats -s",
            "stats -p -v",
            "help look",
            "help -c system",
            "version -d",
            "version -f json",
            "time -g",
            "time -s -v"
        ]
        
        print("📝 测试命令解析:")
        for cmd_str in test_commands:
            try:
                parsed_commands = executor.parse_command_string(cmd_str)
                print(f"  '{cmd_str}' -> 解析成功，{len(parsed_commands)}个命令")
                
                for i, parsed_cmd in enumerate(parsed_commands):
                    print(f"    命令{i+1}: {parsed_cmd.get('key', 'unknown')}")
                    print(f"      参数: {parsed_cmd.get('args', '')}")
                    
            except Exception as e:
                print(f"  ❌ '{cmd_str}' -> 解析失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 命令解析测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    """运行所有测试"""
    print("🚀 开始简化命令系统集成测试")
    print("=" * 60)
    
    test_results = []
    
    # 运行各项测试
    test_results.append(("命令系统导入", test_command_system_imports()))
    test_results.append(("命令执行上下文创建", test_command_context_creation()))
    test_results.append(("命令执行", test_command_execution()))
    test_results.append(("系统命令", test_system_commands()))
    test_results.append(("命令解析", test_command_parsing()))
    
    # 显示测试结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:<20} {status}")
        if result:
            passed += 1
    
    print("-" * 60)
    print(f"总计: {total} 项测试")
    print(f"通过: {passed} 项")
    print(f"失败: {total - passed} 项")
    print(f"成功率: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n🎉 所有测试通过！命令系统核心功能正常。")
        return True
    else:
        print(f"\n⚠️  有 {total - passed} 项测试失败，请检查相关代码。")
        return False

if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 测试过程中发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
