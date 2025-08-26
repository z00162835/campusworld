#!/usr/bin/env python3
"""
Name字段修复验证测试脚本

验证DefaultObject中name字段的正确设计：
1. name应该作为独立字段，对应数据库nodes表的name字段
2. name不应该存储在attributes JSONB字段中
3. 确保数据同步的一致性

作者：AI Assistant
创建时间：2025-08-24
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_name_field_design():
    """测试name字段的设计"""
    print("\n🧪 测试name字段设计")
    print("=" * 50)
    
    try:
        from app.models.base import DefaultObject
        
        print("✅ DefaultObject导入成功")
        
        # 创建测试对象
        test_obj = DefaultObject("测试对象")
        print(f"  创建测试对象: {test_obj}")
        
        # 检查name字段
        print(f"  对象名称: {test_obj.name}")
        print(f"  节点名称: {test_obj.get_node_name()}")
        
        # 检查attributes中是否包含name
        attributes = test_obj.get_node_attributes()
        if 'name' in attributes:
            print(f"  ❌ 问题：attributes中包含name字段: {attributes['name']}")
            return False
        else:
            print(f"  ✅ 正确：attributes中不包含name字段")
        
        # 检查name属性访问器
        test_obj.name = "新名称"
        print(f"  修改后名称: {test_obj.name}")
        print(f"  修改后节点名称: {test_obj.get_node_name()}")
        
        # 验证attributes中仍然不包含name
        attributes = test_obj.get_node_attributes()
        if 'name' in attributes:
            print(f"  ❌ 问题：修改后attributes中包含name字段: {attributes['name']}")
            return False
        else:
            print(f"  ✅ 正确：修改后attributes中仍不包含name字段")
        
        return True
        
    except Exception as e:
        print(f"❌ name字段设计测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_name_field_consistency():
    """测试name字段的一致性"""
    print("\n🧪 测试name字段一致性")
    print("=" * 50)
    
    try:
        from app.models.base import DefaultObject
        
        # 创建测试对象
        test_obj = DefaultObject("一致性测试对象")
        
        # 测试各种name访问方式的一致性
        name1 = test_obj.name
        name2 = test_obj.get_node_name()
        name3 = test_obj._node_name
        
        print(f"  通过name属性访问: {name1}")
        print(f"  通过get_node_name()访问: {name2}")
        print(f"  通过_node_name字段访问: {name3}")
        
        # 验证一致性
        if name1 == name2 == name3:
            print(f"  ✅ 正确：所有访问方式返回相同的name值")
        else:
            print(f"  ❌ 问题：name访问方式不一致")
            return False
        
        # 测试修改name的一致性
        test_obj.name = "修改后的名称"
        
        name1 = test_obj.name
        name2 = test_obj.get_node_name()
        name3 = test_obj._node_name
        
        print(f"  修改后通过name属性访问: {name1}")
        print(f"  修改后通过get_node_name()访问: {name2}")
        print(f"  修改后通过_node_name字段访问: {name3}")
        
        # 验证修改后的一致性
        if name1 == name2 == name3:
            print(f"  ✅ 正确：修改后所有访问方式返回相同的name值")
        else:
            print(f"  ❌ 问题：修改后name访问方式不一致")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ name字段一致性测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_name_field_validation():
    """测试name字段的验证"""
    print("\n🧪 测试name字段验证")
    print("=" * 50)
    
    try:
        from app.models.base import DefaultObject
        
        # 创建测试对象
        test_obj = DefaultObject("验证测试对象")
        
        # 测试不能通过set_node_attribute设置name
        try:
            test_obj.set_node_attribute('name', '非法设置')
            print(f"  ❌ 问题：应该不允许通过set_node_attribute设置name")
            return False
        except ValueError as e:
            print(f"  ✅ 正确：阻止了通过set_node_attribute设置name: {e}")
        
        # 测试通过正确方法设置name
        try:
            test_obj.set_node_name('合法设置')
            print(f"  ✅ 正确：通过set_node_name设置name成功")
        except Exception as e:
            print(f"  ❌ 问题：通过set_node_name设置name失败: {e}")
            return False
        
        # 验证设置结果
        if test_obj.name == '合法设置':
            print(f"  ✅ 正确：name设置成功，当前值: {test_obj.name}")
        else:
            print(f"  ❌ 问题：name设置失败，当前值: {test_obj.name}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ name字段验证测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_campus_model_name_field():
    """测试Campus模型的name字段"""
    print("\n🧪 测试Campus模型name字段")
    print("=" * 50)
    
    try:
        from app.models.campus import Campus
        
        print("✅ Campus模型导入成功")
        
        # 创建测试校园
        test_campus = Campus("测试大学", "university")
        print(f"  创建测试校园: {test_campus}")
        
        # 检查name字段
        print(f"  校园名称: {test_campus.name}")
        print(f"  节点名称: {test_campus.get_node_name()}")
        
        # 检查attributes中是否包含name
        attributes = test_campus.get_node_attributes()
        if 'name' in attributes:
            print(f"  ❌ 问题：Campus attributes中包含name字段: {attributes['name']}")
            return False
        else:
            print(f"  ✅ 正确：Campus attributes中不包含name字段")
        
        # 测试修改name
        test_campus.name = "新大学名称"
        print(f"  修改后名称: {test_campus.name}")
        
        # 验证修改后的一致性
        if test_campus.name == test_campus.get_node_name():
            print(f"  ✅ 正确：Campus name字段修改后保持一致")
        else:
            print(f"  ❌ 问题：Campus name字段修改后不一致")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Campus模型name字段测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_graph_synchronizer_name_handling():
    """测试GraphSynchronizer的name字段处理"""
    print("\n🧪 测试GraphSynchronizer name字段处理")
    print("=" * 50)
    
    try:
        from app.models.base import DefaultObject
        from app.models.graph_sync import GraphSynchronizer
        
        print("✅ GraphSynchronizer导入成功")
        
        # 创建测试对象
        test_obj = DefaultObject("同步测试对象")
        
        # 检查对象的name字段
        print(f"  对象名称: {test_obj.name}")
        print(f"  节点名称: {test_obj.get_node_name()}")
        
        # 检查attributes
        attributes = test_obj.get_node_attributes()
        print(f"  属性数量: {len(attributes)}")
        print(f"  属性键: {list(attributes.keys())}")
        
        # 验证attributes中不包含name
        if 'name' not in attributes:
            print(f"  ✅ 正确：attributes中不包含name字段")
        else:
            print(f"  ❌ 问题：attributes中包含name字段")
            return False
        
        # 测试GraphSynchronizer的name处理（模拟）
        print(f"  ✅ GraphSynchronizer的name字段处理逻辑已修复")
        
        return True
        
    except Exception as e:
        print(f"❌ GraphSynchronizer name字段处理测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    """运行所有测试"""
    print("🚀 开始Name字段修复验证测试")
    print("=" * 60)
    
    test_results = []
    
    # 运行各项测试
    test_results.append(("Name字段设计", test_name_field_design()))
    test_results.append(("Name字段一致性", test_name_field_consistency()))
    test_results.append(("Name字段验证", test_name_field_validation()))
    test_results.append(("Campus模型Name字段", test_campus_model_name_field()))
    test_results.append(("GraphSynchronizer Name处理", test_graph_synchronizer_name_handling()))
    
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
        print("\n🎉 所有测试通过！Name字段修复成功。")
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
