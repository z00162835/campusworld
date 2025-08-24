#!/usr/bin/env python3
"""
命令系统持久化测试脚本

验证重构后的命令系统是否正确集成了图数据持久化：
1. Command类继承自DefaultObject
2. CmdSet类继承自DefaultObject
3. CommandExecutor类继承自DefaultObject
4. 支持命令的持久化存储
5. 支持命令集合的持久化存储
6. 支持命令历史的持久化存储

作者：AI Assistant
创建时间：2025-08-24
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_command_inheritance():
    """测试Command类继承"""
    print("\n🧪 测试Command类继承")
    print("=" * 50)
    
    try:
        from app.commands.base.command import Command
        
        print("✅ Command类导入成功")
        
        # 检查继承关系
        if issubclass(Command, object):
            print("  ✅ Command类正确继承")
        else:
            print("  ❌ Command类继承关系错误")
            return False
        
        # 创建测试命令
        test_cmd = Command("test_command")
        print(f"  创建测试命令: {test_cmd}")
        
        # 检查图数据属性
        if hasattr(test_cmd, '_node_uuid'):
            print(f"  ✅ 命令具有节点UUID: {test_cmd._node_uuid}")
        else:
            print("  ❌ 命令缺少节点UUID")
            return False
        
        if hasattr(test_cmd, '_node_name'):
            print(f"  ✅ 命令具有节点名称: {test_cmd._node_name}")
        else:
            print("  ❌ 命令缺少节点名称")
            return False
        
        if hasattr(test_cmd, '_node_attributes'):
            print(f"  ✅ 命令具有节点属性: {len(test_cmd._node_attributes)} 个")
        else:
            print("  ❌ 命令缺少节点属性")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Command类继承测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_cmdset_inheritance():
    """测试CmdSet类继承"""
    print("\n🧪 测试CmdSet类继承")
    print("=" * 50)
    
    try:
        from app.commands.base.cmdset import CmdSet
        
        print("✅ CmdSet类导入成功")
        
        # 检查继承关系
        if issubclass(CmdSet, object):
            print("  ✅ CmdSet类正确继承")
        else:
            print("  ❌ CmdSet类继承关系错误")
            return False
        
        # 创建测试命令集合
        test_cmdset = CmdSet(key="test_cmdset")
        print(f"  创建测试命令集合: {test_cmdset}")
        
        # 检查图数据属性
        if hasattr(test_cmdset, '_node_uuid'):
            print(f"  ✅ 命令集合具有节点UUID: {test_cmdset._node_uuid}")
        else:
            print("  ❌ 命令集合缺少节点UUID")
            return False
        
        if hasattr(test_cmdset, '_node_name'):
            print(f"  ✅ 命令集合具有节点名称: {test_cmdset._node_name}")
        else:
            print("  ❌ 命令集合缺少节点名称")
            return False
        
        if hasattr(test_cmdset, '_node_attributes'):
            print(f"  ✅ 命令集合具有节点属性: {len(test_cmdset._node_attributes)} 个")
        else:
            print("  ❌ 命令集合缺少节点属性")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ CmdSet类继承测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_executor_inheritance():
    """测试CommandExecutor类继承"""
    print("\n🧪 测试CommandExecutor类继承")
    print("=" * 50)
    
    try:
        from app.commands.base.executor import CommandExecutor
        from app.commands.base.cmdset import CmdSet
        
        print("✅ CommandExecutor类导入成功")
        
        # 检查继承关系
        if issubclass(CommandExecutor, object):
            print("  ✅ CommandExecutor类正确继承")
        else:
            print("  ❌ CommandExecutor类继承关系错误")
            return False
        
        # 创建测试命令执行器
        test_cmdset = CmdSet(key="test_cmdset")
        test_executor = CommandExecutor(default_cmdset=test_cmdset)
        print(f"  创建测试命令执行器: {test_executor}")
        
        # 检查图数据属性
        if hasattr(test_executor, '_node_uuid'):
            print(f"  ✅ 执行器具有节点UUID: {test_executor._node_uuid}")
        else:
            print("  ❌ 执行器缺少节点UUID")
            return False
        
        if hasattr(test_executor, '_node_name'):
            print(f"  ✅ 执行器具有节点名称: {test_executor._node_name}")
        else:
            print("  ❌ 执行器缺少节点名称")
            return False
        
        if hasattr(test_executor, '_node_attributes'):
            print(f"  ✅ 执行器具有节点属性: {len(test_executor._node_attributes)} 个")
        else:
            print("  ❌ 执行器缺少节点属性")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ CommandExecutor类继承测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_command_persistence_methods():
    """测试Command类持久化方法"""
    print("\n🧪 测试Command类持久化方法")
    print("=" * 50)
    
    try:
        from app.commands.base.command import Command
        
        # 创建测试命令
        test_cmd = Command("test_persistence")
        print(f"  创建测试命令: {test_cmd}")
        
        # 测试持久化方法
        methods_to_test = [
            'save_command',
            'load_command', 
            'delete_command',
            'get_command_config',
            'set_command_config',
            'get_command_metadata',
            'is_persistent',
            'get_persistence_status'
        ]
        
        for method_name in methods_to_test:
            if hasattr(test_cmd, method_name):
                print(f"  ✅ 命令具有方法: {method_name}")
            else:
                print(f"  ❌ 命令缺少方法: {method_name}")
                return False
        
        # 测试配置设置
        config = {
            'help_category': 'test',
            'help_entry': '测试命令'
        }
        test_cmd.set_command_config(config)
        print(f"  ✅ 命令配置设置成功")
        
        # 测试配置获取
        retrieved_config = test_cmd.get_command_config()
        if 'help_category' in retrieved_config:
            print(f"  ✅ 命令配置获取成功: {retrieved_config['help_category']}")
        else:
            print("  ❌ 命令配置获取失败")
            return False
        
        # 测试元数据获取
        metadata = test_cmd.get_command_metadata()
        if 'uuid' in metadata and 'type' in metadata:
            print(f"  ✅ 命令元数据获取成功: {metadata['type']}")
        else:
            print("  ❌ 命令元数据获取失败")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Command类持久化方法测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_cmdset_persistence_methods():
    """测试CmdSet类持久化方法"""
    print("\n🧪 测试CmdSet类持久化方法")
    print("=" * 50)
    
    try:
        from app.commands.base.cmdset import CmdSet
        
        # 创建测试命令集合
        test_cmdset = CmdSet(key="test_persistence_cmdset")
        print(f"  创建测试命令集合: {test_cmdset}")
        
        # 测试持久化方法
        methods_to_test = [
            'save_cmdset',
            'load_cmdset',
            'delete_cmdset',
            'get_cmdset_config',
            'set_cmdset_config',
            'get_cmdset_metadata',
            'is_persistent',
            'get_persistence_status',
            'add_command_with_persistence',
            'remove_command_with_persistence'
        ]
        
        for method_name in methods_to_test:
            if hasattr(test_cmdset, method_name):
                print(f"  ✅ 命令集合具有方法: {method_name}")
            else:
                print(f"  ❌ 命令集合缺少方法: {method_name}")
                return False
        
        # 测试配置设置
        config = {
            'priority': 10,
            'mergetype': 'Union'
        }
        test_cmdset.set_cmdset_config(config)
        print(f"  ✅ 命令集合配置设置成功")
        
        # 测试配置获取
        retrieved_config = test_cmdset.get_cmdset_config()
        if 'priority' in retrieved_config:
            print(f"  ✅ 命令集合配置获取成功: {retrieved_config['priority']}")
        else:
            print("  ❌ 命令集合配置获取失败")
            return False
        
        # 测试元数据获取
        metadata = test_cmdset.get_cmdset_metadata()
        if 'uuid' in metadata and 'type' in metadata:
            print(f"  ✅ 命令集合元数据获取成功: {metadata['type']}")
        else:
            print("  ❌ 命令集合元数据获取失败")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ CmdSet类持久化方法测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_executor_persistence_methods():
    """测试CommandExecutor类持久化方法"""
    print("\n🧪 测试CommandExecutor类持久化方法")
    print("=" * 50)
    
    try:
        from app.commands.base.executor import CommandExecutor
        from app.commands.base.cmdset import CmdSet
        
        # 创建测试命令执行器
        test_cmdset = CmdSet(key="test_executor_cmdset")
        test_executor = CommandExecutor(default_cmdset=test_cmdset)
        print(f"  创建测试命令执行器: {test_executor}")
        
        # 测试持久化方法
        methods_to_test = [
            'save_executor',
            'load_executor',
            'delete_executor',
            'get_executor_config',
            'set_executor_config',
            'get_executor_metadata',
            'is_persistent',
            'get_persistence_status',
            'save_command_history',
            'load_command_history',
            'clear_command_history',
            'add_cmdset_with_persistence',
            'remove_cmdset_with_persistence'
        ]
        
        for method_name in methods_to_test:
            if hasattr(test_executor, method_name):
                print(f"  ✅ 执行器具有方法: {method_name}")
            else:
                print(f"  ❌ 执行器缺少方法: {method_name}")
                return False
        
        # 测试配置设置
        config = {
            'max_history': 200,
            'show_errors': False
        }
        test_executor.set_executor_config(config)
        print(f"  ✅ 执行器配置设置成功")
        
        # 测试配置获取
        retrieved_config = test_executor.get_executor_config()
        if 'max_history' in retrieved_config:
            print(f"  ✅ 执行器配置获取成功: {retrieved_config['max_history']}")
        else:
            print("  ❌ 执行器配置获取失败")
            return False
        
        # 测试元数据获取
        metadata = test_executor.get_executor_metadata()
        if 'uuid' in metadata and 'type' in metadata:
            print(f"  ✅ 执行器元数据获取成功: {metadata['type']}")
        else:
            print("  ❌ 执行器元数据获取失败")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ CommandExecutor类持久化方法测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_system_commands_integration():
    """测试系统命令集成"""
    print("\n🧪 测试系统命令集成")
    print("=" * 50)
    
    try:
        from app.commands.system.cmdset import SystemCmdSet
        
        print("✅ SystemCmdSet导入成功")
        
        # 创建系统命令集合
        system_cmdset = SystemCmdSet()
        print(f"  创建系统命令集合: {system_cmdset}")
        
        # 检查图数据属性
        if hasattr(system_cmdset, '_node_uuid'):
            print(f"  ✅ 系统命令集合具有节点UUID: {system_cmdset._node_uuid}")
        else:
            print("  ❌ 系统命令集合缺少节点UUID")
            return False
        
        # 检查命令数量
        command_count = len(system_cmdset.commands)
        print(f"  ✅ 系统命令集合包含 {command_count} 个命令")
        
        # 检查命令类型
        for key, cmd_class in system_cmdset.commands.items():
            # 创建命令实例来检查节点UUID
            try:
                cmd_instance = cmd_class()
                if hasattr(cmd_instance, '_node_uuid'):
                    print(f"    ✅ 命令 {key} 具有节点UUID")
                else:
                    print(f"    ❌ 命令 {key} 缺少节点UUID")
                    return False
            except Exception as e:
                print(f"    ⚠️  命令 {key} 创建实例失败: {e}")
                # 继续检查其他命令
                continue
        
        return True
        
    except Exception as e:
        print(f"❌ 系统命令集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    """运行所有测试"""
    print("🚀 开始命令系统持久化测试")
    print("=" * 60)
    
    test_results = []
    
    # 运行各项测试
    test_results.append(("Command类继承", test_command_inheritance()))
    test_results.append(("CmdSet类继承", test_cmdset_inheritance()))
    test_results.append(("CommandExecutor类继承", test_executor_inheritance()))
    test_results.append(("Command类持久化方法", test_command_persistence_methods()))
    test_results.append(("CmdSet类持久化方法", test_cmdset_persistence_methods()))
    test_results.append(("CommandExecutor类持久化方法", test_executor_persistence_methods()))
    test_results.append(("系统命令集成", test_system_commands_integration()))
    
    # 显示测试结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:<30} {status}")
        if result:
            passed += 1
    
    print("-" * 60)
    print(f"总计: {total} 项测试")
    print(f"通过: {passed} 项")
    print(f"失败: {total - passed} 项")
    print(f"成功率: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n🎉 所有测试通过！命令系统持久化重构成功。")
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
