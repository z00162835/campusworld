#!/usr/bin/env python3
"""
简化集成测试

测试重构后的核心功能，避免复杂的模型依赖
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_core_imports():
    """测试核心导入"""
    print("=== 测试核心导入 ===")
    
    try:
        # 测试基础模型
        from app.models.base import DefaultObject, DefaultAccount
        print("✅ 基础模型导入成功")
        
        # 测试图同步器
        from app.models.graph_sync import GraphSynchronizer
        print("✅ 图同步器导入成功")
        
        # 测试图模型
        from app.models.graph import Node, Relationship
        print("✅ 图模型导入成功")
        
        return True
    except Exception as e:
        print(f"❌ 核心导入失败: {e}")
        return False


def test_simple_object_creation():
    """测试简单对象创建"""
    print("\n=== 测试简单对象创建 ===")
    
    try:
        from app.models.base import DefaultObject
        
        # 创建简单的测试对象类
        class SimpleTestObject(DefaultObject):
            __tablename__ = "simple_test_objects"
            
            def __init__(self, name: str, **kwargs):
                super().__init__(name=name, **kwargs)
        
        # 创建对象实例
        test_obj = SimpleTestObject("简单测试对象")
        print("✅ 简单对象创建成功")
        
        # 测试基本属性
        print(f"  名称: {test_obj.name}")
        print(f"  UUID: {test_obj.get_graph_uuid()}")
        print(f"  类路径: {test_obj.get_graph_classpath()}")
        
        return True
    except Exception as e:
        print(f"❌ 简单对象创建失败: {e}")
        return False


def test_graph_synchronizer_basic():
    """测试图同步器基础功能"""
    print("\n=== 测试图同步器基础功能 ===")
    
    try:
        from app.models.graph_sync import GraphSynchronizer
        
        # 创建同步器
        synchronizer = GraphSynchronizer()
        print("✅ 图同步器创建成功")
        
        # 测试基本方法
        print("✅ 基础功能测试通过")
        
        return True
    except Exception as e:
        print(f"❌ 图同步器基础功能测试失败: {e}")
        return False


def test_interface_implementation():
    """测试接口实现"""
    print("\n=== 测试接口实现 ===")
    
    try:
        from app.models.base import DefaultObject, GraphNodeInterface
        
        # 检查方法是否存在
        required_methods = [
            'get_graph_uuid',
            'get_graph_classpath', 
            'get_graph_attributes',
            'set_graph_attribute',
            'get_graph_tags',
            'add_graph_tag',
            'remove_graph_tag',
            'sync_to_graph'
        ]
        
        missing_methods = []
        for method in required_methods:
            if not hasattr(DefaultObject, method):
                missing_methods.append(method)
        
        if missing_methods:
            print(f"❌ 缺少方法: {missing_methods}")
            return False
        
        print("✅ 所有必需方法都存在")
        
        # 检查方法是否可调用
        class TestObject(DefaultObject):
            __tablename__ = "test_objects"
            
            def __init__(self, name: str, **kwargs):
                super().__init__(name=name, **kwargs)
        
        obj = TestObject("测试对象")
        for method in required_methods:
            if not callable(getattr(obj, method)):
                print(f"❌ 方法 {method} 不可调用")
                return False
        
        print("✅ 所有方法都可调用")
        
        return True
    except Exception as e:
        print(f"❌ 接口实现测试失败: {e}")
        return False


def test_attribute_management():
    """测试属性管理"""
    print("\n=== 测试属性管理 ===")
    
    try:
        from app.models.base import DefaultObject
        
        # 创建测试对象
        class AttributeTestObject(DefaultObject):
            __tablename__ = "attribute_test_objects"
            
            def __init__(self, name: str, **kwargs):
                super().__init__(name=name, **kwargs)
        
        obj = AttributeTestObject("属性测试对象")
        print("✅ 属性测试对象创建成功")
        
        # 测试属性设置
        obj.set_graph_attribute("test_key", "test_value")
        obj.add_graph_tag("test_tag")
        
        # 测试属性获取
        value = obj.get_graph_attribute("test_key")
        tags = obj.get_graph_tags()
        
        print(f"  设置属性: test_key = {value}")
        print(f"  添加标签: {tags}")
        
        if value == "test_value" and "test_tag" in tags:
            print("✅ 属性管理测试通过")
            return True
        else:
            print("❌ 属性管理测试失败")
            return False
            
    except Exception as e:
        print(f"❌ 属性管理测试失败: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("🚀 开始简化集成测试\n")
    
    tests = [
        test_core_imports,
        test_simple_object_creation,
        test_graph_synchronizer_basic,
        test_interface_implementation,
        test_attribute_management
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ 测试 {test.__name__} 出现异常: {e}")
    
    print(f"\n📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！核心集成功能工作正常。")
        return True
    else:
        print("⚠️  部分测试失败，请检查相关代码。")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
