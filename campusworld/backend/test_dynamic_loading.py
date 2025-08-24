#!/usr/bin/env python3
"""
测试命令配置动态加载功能

验证从数据库动态加载命令和命令集合配置的功能
包括缓存机制和热更新功能

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

def test_command_loader():
    """测试命令加载器"""
    print("\n🧪 测试命令加载器")
    print("=" * 50)
    
    try:
        from app.commands.loaders import command_loader
        
        print("✅ CommandLoader导入成功")
        
        # 测试加载单个命令配置
        print("\n📋 测试加载单个命令配置")
        print("-" * 30)
        
        look_config = command_loader.load_command_config('look')
        if look_config:
            print(f"  ✅ 成功加载look命令配置")
            print(f"     - 命令键: {look_config['key']}")
            print(f"     - 描述: {look_config['description'][:50]}...")
            print(f"     - 分类: {look_config['attributes'].get('help_category', 'unknown')}")
            print(f"     - 别名: {look_config['attributes'].get('command_aliases', [])}")
            print(f"     - 加载时间: {look_config['loaded_at']}")
        else:
            print("  ❌ 加载look命令配置失败")
            return False
        
        # 测试加载所有命令配置
        print("\n📋 测试加载所有命令配置")
        print("-" * 30)
        
        all_commands = command_loader.load_all_command_configs()
        if all_commands:
            print(f"  ✅ 成功加载 {len(all_commands)} 个命令配置")
            for cmd_key, cmd_config in all_commands.items():
                print(f"     - {cmd_key}: {cmd_config['attributes'].get('help_category', 'unknown')}")
        else:
            print("  ❌ 加载所有命令配置失败")
            return False
        
        # 测试按分类加载命令
        print("\n📋 测试按分类加载命令")
        print("-" * 30)
        
        system_commands = command_loader.load_commands_by_category('system')
        if system_commands:
            print(f"  ✅ 成功加载系统分类的 {len(system_commands)} 个命令")
            for cmd_key in system_commands.keys():
                print(f"     - {cmd_key}")
        else:
            print("  ❌ 加载系统分类命令失败")
            return False
        
        # 测试缓存机制
        print("\n📋 测试缓存机制")
        print("-" * 30)
        
        # 第一次加载（应该从数据库）
        start_time = datetime.now()
        command_loader.load_command_config('stats', force_reload=True)
        first_load_time = (datetime.now() - start_time).total_seconds()
        
        # 第二次加载（应该从缓存）
        start_time = datetime.now()
        command_loader.load_command_config('stats', force_reload=False)
        second_load_time = (datetime.now() - start_time).total_seconds()
        
        print(f"  ✅ 第一次加载时间: {first_load_time:.4f}秒")
        print(f"  ✅ 第二次加载时间: {second_load_time:.4f}秒")
        print(f"  ✅ 缓存加速比: {first_load_time/second_load_time:.2f}x")
        
        # 测试缓存信息
        cache_info = command_loader.get_cache_info()
        print(f"  ✅ 缓存大小: {cache_info['command_cache_size']}")
        print(f"  ✅ 缓存TTL: {cache_info['cache_ttl']}秒")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试命令加载器失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_cmdset_loader():
    """测试命令集合加载器"""
    print("\n🧪 测试命令集合加载器")
    print("=" * 50)
    
    try:
        from app.commands.loaders import cmdset_loader
        
        print("✅ CmdSetLoader导入成功")
        
        # 测试加载命令集合配置
        print("\n📋 测试加载命令集合配置")
        print("-" * 30)
        
        system_cmdset_config = cmdset_loader.load_cmdset_config('system_cmdset')
        if system_cmdset_config:
            print(f"  ✅ 成功加载system_cmdset配置")
            print(f"     - 集合键: {system_cmdset_config['key']}")
            print(f"     - 描述: {system_cmdset_config['description']}")
            print(f"     - 合并类型: {system_cmdset_config['attributes'].get('cmdset_mergetype', 'unknown')}")
            print(f"     - 优先级: {system_cmdset_config['attributes'].get('cmdset_priority', 'unknown')}")
            print(f"     - 加载时间: {system_cmdset_config['loaded_at']}")
        else:
            print("  ❌ 加载system_cmdset配置失败")
            return False
        
        # 测试加载命令集合包含的命令
        print("\n📋 测试加载命令集合包含的命令")
        print("-" * 30)
        
        system_commands = cmdset_loader.load_cmdset_commands('system_cmdset')
        if system_commands:
            print(f"  ✅ 成功加载system_cmdset的 {len(system_commands)} 个命令")
            for cmd_info in system_commands:
                print(f"     - {cmd_info['key']}: {cmd_info['attributes'].get('help_category', 'unknown')}")
                print(f"       关系: {cmd_info['relationship'].get('command_class', 'unknown')}")
        else:
            print("  ❌ 加载system_cmdset命令失败")
            return False
        
        # 测试加载所有命令集合配置
        print("\n📋 测试加载所有命令集合配置")
        print("-" * 30)
        
        all_cmdsets = cmdset_loader.load_all_cmdset_configs()
        if all_cmdsets:
            print(f"  ✅ 成功加载 {len(all_cmdsets)} 个命令集合配置")
            for cmdset_key, cmdset_config in all_cmdsets.items():
                print(f"     - {cmdset_key}: {cmdset_config['description']}")
        else:
            print("  ❌ 加载所有命令集合配置失败")
            return False
        
        # 测试缓存机制
        print("\n📋 测试缓存机制")
        print("-" * 30)
        
        # 第一次加载（应该从数据库）
        start_time = datetime.now()
        cmdset_loader.load_cmdset_config('system_cmdset', force_reload=True)
        first_load_time = (datetime.now() - start_time).total_seconds()
        
        # 第二次加载（应该从缓存）
        start_time = datetime.now()
        cmdset_loader.load_cmdset_config('system_cmdset', force_reload=False)
        second_load_time = (datetime.now() - start_time).total_seconds()
        
        print(f"  ✅ 第一次加载时间: {first_load_time:.4f}秒")
        print(f"  ✅ 第二次加载时间: {second_load_time:.4f}秒")
        print(f"  ✅ 缓存加速比: {first_load_time/second_load_time:.2f}x")
        
        # 测试缓存信息
        cache_info = cmdset_loader.get_cache_info()
        print(f"  ✅ 缓存大小: {cache_info['cmdset_cache_size']}")
        print(f"  ✅ 缓存TTL: {cache_info['cache_ttl']}秒")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试命令集合加载器失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_integration():
    """测试集成功能"""
    print("\n🧪 测试集成功能")
    print("=" * 50)
    
    try:
        from app.commands.loaders import command_loader, cmdset_loader
        
        print("✅ 加载器集成测试")
        
        # 测试命令和命令集合的关联
        print("\n📋 测试命令和命令集合的关联")
        print("-" * 30)
        
        # 加载系统命令集合
        system_cmdset = cmdset_loader.load_cmdset_config('system_cmdset')
        if not system_cmdset:
            print("  ❌ 无法加载系统命令集合")
            return False
        
        # 加载系统命令集合包含的命令
        system_commands = cmdset_loader.load_cmdset_commands('system_cmdset')
        if not system_commands:
            print("  ❌ 无法加载系统命令集合的命令")
            return False
        
        print(f"  ✅ 系统命令集合: {system_cmdset['key']}")
        print(f"  ✅ 包含命令数量: {len(system_commands)}")
        
        # 验证每个命令的配置
        for cmd_info in system_commands:
            cmd_key = cmd_info['key']
            cmd_config = command_loader.load_command_config(cmd_key)
            
            if cmd_config:
                print(f"     ✅ {cmd_key}: {cmd_config['attributes'].get('help_category', 'unknown')}")
                
                # 验证命令属性的一致性
                if cmd_config['key'] == cmd_info['key']:
                    print(f"        - 配置一致")
                else:
                    print(f"        - 配置不一致")
            else:
                print(f"     ❌ {cmd_key}: 无法加载配置")
        
        # 测试缓存清理
        print("\n📋 测试缓存清理")
        print("-" * 30)
        
        # 清理指定缓存
        command_loader.clear_cache('command_look')
        print("  ✅ 清理指定命令缓存")
        
        # 清理所有缓存
        cmdset_loader.clear_cache()
        print("  ✅ 清理所有命令集合缓存")
        
        # 验证缓存已清理
        cmdset_cache_info = cmdset_loader.get_cache_info()
        print(f"  ✅ 命令集合缓存大小: {cmdset_cache_info['cmdset_cache_size']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试集成功能失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_tests():
    """运行所有测试"""
    print("🚀 开始测试命令配置动态加载功能")
    print("=" * 60)
    
    test_functions = [
        ("命令加载器测试", test_command_loader),
        ("命令集合加载器测试", test_cmdset_loader),
        ("集成功能测试", test_integration)
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
        print("\n🎉 所有测试通过！命令配置动态加载功能正常")
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
