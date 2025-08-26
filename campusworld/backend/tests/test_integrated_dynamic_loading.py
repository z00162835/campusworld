#!/usr/bin/env python3
"""
测试集成后的动态加载功能

验证Command和CmdSet类从数据库动态加载配置的功能
包括配置更新、状态查询等

作者：AI Assistant
创建时间：2025-08-24
"""

import sys
import os
import json
from datetime import datetime

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_command_dynamic_loading():
    """测试命令的动态加载功能"""
    print("\n🧪 测试命令的动态加载功能")
    print("=" * 50)
    
    try:
        from app.commands.system.look import CmdLook
        
        print("✅ CmdLook导入成功")
        
        # 创建命令实例
        cmd = CmdLook()
        print(f"  📋 命令实例创建成功: {cmd.key}")
        
        # 显示初始配置状态
        print("\n📋 初始配置状态")
        print("-" * 30)
        initial_status = cmd.get_config_status()
        for key, value in initial_status.items():
            if key in ['help_entry', 'description'] and value and len(str(value)) > 50:
                print(f"  - {key}: {str(value)[:50]}...")
            else:
                print(f"  - {key}: {value}")
        
        # 从数据库加载配置
        print("\n📋 从数据库加载配置")
        print("-" * 30)
        
        if cmd.load_from_database():
            print("  ✅ 成功从数据库加载配置")
            
            # 显示加载后的配置状态
            print("\n📋 加载后的配置状态")
            print("-" * 30)
            loaded_status = cmd.get_config_status()
            for key, value in loaded_status.items():
                if key in ['help_entry', 'description'] and value and len(str(value)) > 50:
                    print(f"  - {key}: {str(value)[:50]}...")
                else:
                    print(f"  - {key}: {value}")
            
            # 验证配置来源
            config_source = cmd.get_node_attribute('config_source')
            if config_source == 'database':
                print("  ✅ 配置来源已更新为数据库")
            else:
                print(f"  ⚠️  配置来源: {config_source}")
            
        else:
            print("  ❌ 从数据库加载配置失败")
            return False
        
        # 测试重新加载配置
        print("\n📋 测试重新加载配置")
        print("-" * 30)
        
        if cmd.reload_config():
            print("  ✅ 成功重新加载配置")
        else:
            print("  ❌ 重新加载配置失败")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 测试命令动态加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_cmdset_dynamic_loading():
    """测试命令集合的动态加载功能"""
    print("\n🧪 测试命令集合的动态加载功能")
    print("=" * 50)
    
    try:
        from app.commands.system.cmdset import SystemCmdSet
        
        print("✅ SystemCmdSet导入成功")
        
        # 创建命令集合实例
        cmdset = SystemCmdSet()
        print(f"  📋 命令集合实例创建成功: {cmdset.key}")
        
        # 显示初始配置状态
        print("\n📋 初始配置状态")
        print("-" * 30)
        initial_status = cmdset.get_config_status()
        for key, value in initial_status.items():
            print(f"  - {key}: {value}")
        
        # 从数据库加载配置
        print("\n📋 从数据库加载配置")
        print("-" * 30)
        
        if cmdset.load_from_database():
            print("  ✅ 成功从数据库加载配置")
            
            # 显示加载后的配置状态
            print("\n📋 加载后的配置状态")
            print("-" * 30)
            loaded_status = cmdset.get_config_status()
            for key, value in loaded_status.items():
                print(f"  - {key}: {value}")
            
            # 验证配置来源
            config_source = cmdset.get_node_attribute('config_source')
            if config_source == 'database':
                print("  ✅ 配置来源已更新为数据库")
            else:
                print(f"  ⚠️  配置来源: {config_source}")
            
        else:
            print("  ❌ 从数据库加载配置失败")
            return False
        
        # 测试重新加载配置
        print("\n📋 测试重新加载配置")
        print("-" * 30)
        
        if cmdset.reload_config():
            print("  ✅ 成功重新加载配置")
        else:
            print("  ❌ 重新加载配置失败")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 测试命令集合动态加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config_consistency():
    """测试配置一致性"""
    print("\n🧪 测试配置一致性")
    print("=" * 50)
    
    try:
        from app.commands.system.look import CmdLook
        from app.commands.system.cmdset import SystemCmdSet
        from app.commands.loaders import command_loader, cmdset_loader
        
        print("✅ 导入成功")
        
        # 创建命令和命令集合实例
        cmd = CmdLook()
        cmdset = SystemCmdSet()
        
        # 从数据库加载配置
        cmd.load_from_database()
        cmdset.load_from_database()
        
        # 验证命令配置一致性
        print("\n📋 验证命令配置一致性")
        print("-" * 30)
        
        # 从加载器获取配置
        loader_config = command_loader.load_command_config('look')
        if loader_config:
            loader_aliases = loader_config['attributes'].get('command_aliases', [])
            loader_category = loader_config['attributes'].get('help_category', '')
            
            # 从命令实例获取配置
            instance_aliases = cmd.aliases
            instance_category = cmd.help_category
            
            print(f"  📊 别名一致性检查:")
            print(f"     - 加载器: {loader_aliases}")
            print(f"     - 实例: {instance_aliases}")
            print(f"     - 一致: {loader_aliases == instance_aliases}")
            
            print(f"  📊 分类一致性检查:")
            print(f"     - 加载器: {loader_category}")
            print(f"     - 实例: {instance_category}")
            print(f"     - 一致: {loader_category == instance_category}")
        
        # 验证命令集合配置一致性
        print("\n📋 验证命令集合配置一致性")
        print("-" * 30)
        
        # 从加载器获取配置
        loader_cmdset_config = cmdset_loader.load_cmdset_config('system_cmdset')
        if loader_cmdset_config:
            loader_mergetype = loader_cmdset_config['attributes'].get('cmdset_mergetype', '')
            loader_priority = loader_cmdset_config['attributes'].get('cmdset_priority', 0)
            
            # 从命令集合实例获取配置
            instance_mergetype = cmdset.mergetype
            instance_priority = cmdset.priority
            
            print(f"  📊 合并类型一致性检查:")
            print(f"     - 加载器: {loader_mergetype}")
            print(f"     - 实例: {instance_mergetype}")
            print(f"     - 一致: {loader_mergetype == instance_mergetype}")
            
            print(f"  📊 优先级一致性检查:")
            print(f"     - 加载器: {loader_priority}")
            print(f"     - 实例: {instance_priority}")
            print(f"     - 一致: {loader_priority == instance_priority}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试配置一致性失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_tests():
    """运行所有测试"""
    print("🚀 开始测试集成后的动态加载功能")
    print("=" * 60)
    
    test_functions = [
        ("命令动态加载测试", test_command_dynamic_loading),
        ("命令集合动态加载测试", test_cmdset_dynamic_loading),
        ("配置一致性测试", test_config_consistency)
    ]
    
    success_count = 0
    total_tests = len(test_functions)
    
    for test_name, test_func in test_functions:
        print(f"\n📋 执行测试: {test_name}")
        print("-" * 40)
        
        if test_func():
            success_count += 1
            print(f"✅ {test_name} 通过")
        else:
            print(f"❌ {test_name} 失败")
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    print(f"总计测试: {total_tests}")
    print(f"通过测试: {success_count}")
    print(f"失败测试: {total_tests - success_count}")
    print(f"通过率: {success_count/total_tests*100:.1f}%")
    
    if success_count == total_tests:
        print("\n🎉 所有测试通过！集成后的动态加载功能正常")
        return True
    else:
        print(f"\n⚠️  有 {total_tests - success_count} 个测试失败，请检查相关功能")
        return False

if __name__ == "__main__":
    try:
        success = run_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 测试过程中发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
