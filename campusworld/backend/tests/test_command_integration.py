#!/usr/bin/env python3
"""
命令系统集成测试脚本

测试命令系统与DefaultObject的集成，验证对象能够使用命令系统
包括命令执行、权限检查、上下文管理等

作者：AI Assistant
创建时间：2025-08-24
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_default_object_command_integration():
    """测试DefaultObject的命令系统集成"""
    print("\n🧪 测试DefaultObject命令系统集成")
    print("=" * 50)
    
    try:
        from app.models.base import DefaultObject
        
        print("✅ DefaultObject导入成功")
        
        # 创建测试对象
        test_obj = DefaultObject("测试对象")
        print(f"  创建测试对象: {test_obj}")
        
        # 测试命令集合
        cmdset = test_obj.get_cmdset()
        print(f"  命令集合: {cmdset}")
        
        # 测试命令执行
        result = test_obj.execute_command("help")
        print(f"  执行help命令结果: {result}")
        
        # 测试命令历史
        history = test_obj.get_command_history()
        print(f"  命令历史数量: {len(history)}")
        
        # 测试可用命令
        available_commands = test_obj.get_available_commands()
        print(f"  可用命令: {available_commands}")
        
        return True
        
    except Exception as e:
        print(f"❌ DefaultObject命令系统集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_campus_command_integration():
    """测试Campus模型的命令系统集成"""
    print("\n🧪 测试Campus模型命令系统集成")
    print("=" * 50)
    
    try:
        from app.models.campus import Campus
        
        print("✅ Campus模型导入成功")
        
        # 创建测试校园
        test_campus = Campus("测试大学", "university")
        print(f"  创建测试校园: {test_campus}")
        
        # 测试命令集合
        cmdset = test_campus.get_cmdset()
        print(f"  命令集合: {cmdset}")
        
        # 测试命令执行
        result = test_campus.execute_command("version")
        print(f"  执行version命令结果: {result}")
        
        # 测试校园特定方法
        test_campus.add_department("计算机学院", "academic")
        test_campus.add_facility("图书馆", "library")
        
        departments = test_campus.get_departments()
        facilities = test_campus.get_facilities()
        
        print(f"  部门数量: {len(departments)}")
        print(f"  设施数量: {len(facilities)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Campus模型命令系统集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_command_context():
    """测试命令执行上下文"""
    print("\n🧪 测试命令执行上下文")
    print("=" * 50)
    
    try:
        from app.commands.context import CommandContext, CommandExecutionContext
        
        print("✅ 命令执行上下文导入成功")
        
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
        
        # 测试权限检查
        context.require_permission("admin")
        context.require_role("moderator")
        
        validation = context.validate_context()
        print(f"  上下文验证: {validation}")
        
        return True
        
    except Exception as e:
        print(f"❌ 命令执行上下文测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_command_execution_flow():
    """测试完整命令执行流程"""
    print("\n🧪 测试完整命令执行流程")
    print("=" * 50)
    
    try:
        from app.models.campus import Campus
        from app.commands.context import CommandExecutionContext
        
        print("✅ 开始测试完整命令执行流程")
        
        # 创建校园对象
        campus = Campus("集成测试大学", "university")
        print(f"  创建校园: {campus.name}")
        
        # 创建执行环境
        exec_env = CommandExecutionContext()
        
        # 创建执行上下文
        context = exec_env.create_context(
            caller=campus,
            target=campus,
            location=campus
        )
        
        # 设置权限要求
        context.require_permission("campus_admin")
        context.set_access_level("admin")
        
        # 验证上下文
        validation = context.validate_context()
        print(f"  上下文验证结果: {validation}")
        
        # 执行命令
        result = campus.execute_command("stats -s", caller=campus)
        print(f"  命令执行结果: {result}")
        
        # 检查命令历史
        history = campus.get_command_history()
        print(f"  命令历史记录: {len(history)}条")
        
        # 获取上下文统计
        context_stats = exec_env.get_context_statistics()
        print(f"  执行环境统计: {context_stats}")
        
        return True
        
    except Exception as e:
        print(f"❌ 完整命令执行流程测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    """运行所有测试"""
    print("🚀 开始命令系统集成测试")
    print("=" * 60)
    
    test_results = []
    
    # 运行各项测试
    test_results.append(("DefaultObject命令集成", test_default_object_command_integration()))
    test_results.append(("Campus模型命令集成", test_campus_command_integration()))
    test_results.append(("命令执行上下文", test_command_context()))
    test_results.append(("完整命令执行流程", test_command_execution_flow()))
    
    # 显示测试结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:<25} {status}")
        if result:
            passed += 1
    
    print("-" * 60)
    print(f"总计: {total} 项测试")
    print(f"通过: {passed} 项")
    print(f"失败: {total - passed} 项")
    print(f"成功率: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n🎉 所有测试通过！命令系统集成成功。")
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
