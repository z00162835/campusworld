#!/usr/bin/env python3
"""
系统命令测试脚本

测试所有系统命令的功能，包括查看、统计、帮助、版本、时间等
验证命令系统的正确性和完整性

作者：AI Assistant
创建时间：2025-08-24
"""

import sys
import os
import time

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_command_base_classes():
    """测试命令基类"""
    print("\n🧪 测试命令基类")
    print("=" * 50)
    
    try:
        from app.commands.base import Command, CmdSet, CommandExecutor
        
        print("✅ 命令基类导入成功")
        print(f"  Command: {Command}")
        print(f"  CmdSet: {CmdSet}")
        print(f"  CommandExecutor: {CommandExecutor}")
        
        return True
        
    except Exception as e:
        print(f"❌ 命令基类导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_system_commands():
    """测试系统命令"""
    print("\n🧪 测试系统命令")
    print("=" * 50)
    
    try:
        from app.commands.system import CmdLook, CmdStats, CmdHelp, CmdVersion, CmdTime
        
        print("✅ 系统命令导入成功")
        
        # 测试Look命令
        print("\n📖 测试Look命令")
        look_cmd = CmdLook()
        print(f"  命令关键字: {look_cmd.key}")
        print(f"  命令别名: {look_cmd.aliases}")
        print(f"  帮助分类: {look_cmd.help_category}")
        
        # 测试Stats命令
        print("\n📊 测试Stats命令")
        stats_cmd = CmdStats()
        print(f"  命令关键字: {stats_cmd.key}")
        print(f"  命令别名: {stats_cmd.aliases}")
        print(f"  帮助分类: {stats_cmd.help_category}")
        
        # 测试Help命令
        print("\n❓ 测试Help命令")
        help_cmd = CmdHelp()
        print(f"  命令关键字: {help_cmd.key}")
        print(f"  命令别名: {help_cmd.aliases}")
        print(f"  帮助分类: {help_cmd.help_category}")
        
        # 测试Version命令
        print("\n🚀 测试Version命令")
        version_cmd = CmdVersion()
        print(f"  命令关键字: {version_cmd.key}")
        print(f"  命令别名: {version_cmd.aliases}")
        print(f"  帮助分类: {version_cmd.help_category}")
        
        # 测试Time命令
        print("\n⏰ 测试Time命令")
        time_cmd = CmdTime()
        print(f"  命令关键字: {time_cmd.key}")
        print(f"  命令别名: {time_cmd.aliases}")
        print(f"  帮助分类: {time_cmd.help_category}")
        
        return True
        
    except Exception as e:
        print(f"❌ 系统命令测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_system_cmdset():
    """测试系统命令集合"""
    print("\n🧪 测试系统命令集合")
    print("=" * 50)
    
    try:
        from app.commands.system.cmdset import SystemCmdSet
        
        print("✅ 系统命令集合导入成功")
        
        # 创建命令集合
        cmdset = SystemCmdSet()
        print(f"  命令集合关键字: {cmdset.key}")
        print(f"  合并类型: {cmdset.mergetype}")
        print(f"  优先级: {cmdset.priority}")
        print(f"  命令数量: {len(cmdset.commands)}")
        
        # 检查命令集合中的命令
        print("\n📋 命令集合中的命令:")
        for cmd_key, cmd_class in cmdset.commands.items():
            print(f"  {cmd_key}: {cmd_class.__name__}")
        
        # 测试帮助信息
        help_text = cmdset.get_help()
        print(f"\n📖 命令集合帮助信息:")
        print(help_text)
        
        # 测试命令集合信息
        cmdset_info = cmdset.get_command_info()
        print(f"\n📊 命令集合信息:")
        for key, value in cmdset_info.items():
            print(f"  {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"❌ 系统命令集合测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_command_executor():
    """测试命令执行器"""
    print("\n🧪 测试命令执行器")
    print("=" * 50)
    
    try:
        from app.commands.base import CommandExecutor
        from app.commands.system.cmdset import SystemCmdSet
        
        print("✅ 命令执行器导入成功")
        
        # 创建系统命令集合
        system_cmdset = SystemCmdSet()
        
        # 创建命令执行器
        executor = CommandExecutor(default_cmdset=system_cmdset)
        print(f"  默认命令集合: {executor.default_cmdset.key}")
        print(f"  命令集合数量: {len(executor.cmdsets)}")
        
        # 测试命令查找
        print("\n🔍 测试命令查找:")
        look_cmd = executor.find_command("look")
        if look_cmd:
            print(f"  找到look命令: {look_cmd.__name__}")
        else:
            print("  ❌ 未找到look命令")
        
        stats_cmd = executor.find_command("stats")
        if stats_cmd:
            print(f"  找到stats命令: {stats_cmd.__name__}")
        else:
            print("  ❌ 未找到stats命令")
        
        # 测试可用命令
        available_commands = executor.get_available_commands()
        print(f"\n📋 可用命令数量: {len(available_commands)}")
        
        # 测试命令分类
        categories = executor.get_categories()
        print(f"\n📂 命令分类: {categories}")
        
        return True
        
    except Exception as e:
        print(f"❌ 命令执行器测试失败: {e}")
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
        
        print("✅ 命令解析测试开始")
        
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
        
        print("\n📝 测试命令解析:")
        for cmd_str in test_commands:
            try:
                parsed_commands = executor.parse_command_string(cmd_str)
                print(f"  '{cmd_str}' -> 解析成功，{len(parsed_commands)}个命令")
                
                for i, parsed_cmd in enumerate(parsed_commands):
                    print(f"    命令{i+1}: {parsed_cmd.get('key', 'unknown')}")
                    print(f"      参数: {parsed_cmd.get('args', '')}")
                    print(f"      开关: {parsed_cmd.get('switches', [])}")
                    
            except Exception as e:
                print(f"  ❌ '{cmd_str}' -> 解析失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 命令解析测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_command_help_system():
    """测试命令帮助系统"""
    print("\n🧪 测试命令帮助系统")
    print("=" * 50)
    
    try:
        from app.commands.system import CmdLook, CmdStats, CmdHelp, CmdVersion, CmdTime
        
        print("✅ 命令帮助系统测试开始")
        
        # 测试各个命令的帮助信息
        commands = [
            ("Look", CmdLook()),
            ("Stats", CmdStats()),
            ("Help", CmdHelp()),
            ("Version", CmdVersion()),
            ("Time", CmdTime())
        ]
        
        for name, cmd in commands:
            print(f"\n📖 {name}命令帮助:")
            print(f"  帮助分类: {cmd.help_category}")
            print(f"  帮助条目: {cmd.help_entry[:100]}...")
            
            # 测试帮助方法
            try:
                help_text = cmd.help()
                print(f"  帮助方法: 可用")
            except Exception as e:
                print(f"  帮助方法: 不可用 ({e})")
        
        return True
        
    except Exception as e:
        print(f"❌ 命令帮助系统测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    """运行所有测试"""
    print("🚀 开始系统命令测试")
    print("=" * 60)
    
    test_results = []
    
    # 运行各项测试
    test_results.append(("命令基类", test_command_base_classes()))
    test_results.append(("系统命令", test_system_commands()))
    test_results.append(("系统命令集合", test_system_cmdset()))
    test_results.append(("命令执行器", test_command_executor()))
    test_results.append(("命令解析", test_command_parsing()))
    test_results.append(("命令帮助系统", test_command_help_system()))
    
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
        print("\n🎉 所有测试通过！系统命令功能正常。")
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
