#!/usr/bin/env python3
"""
图模型系统测试

测试图模型的核心功能，包括：
- 基础类型导入
- 类型层次结构
- 关系类型系统
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_basic_imports():
    """测试基础导入"""
    print("=== 测试基础导入 ===")
    
    try:
        from app.models.graph import (
            BaseNode, BaseRelationship, 
            Node, Relationship, 
            FriendshipRelationship, LocationRelationship, OwnershipRelationship
        )
        print("✅ 基础类型导入成功")
        
        # 测试类型层次
        print(f"  Node 是 BaseNode 的子类: {issubclass(Node, BaseNode)}")
        print(f"  Relationship 是 BaseRelationship 的子类: {issubclass(Relationship, BaseRelationship)}")
        print(f"  FriendshipRelationship 是 Relationship 的子类: {issubclass(FriendshipRelationship, Relationship)}")
        
        return True
    except Exception as e:
        print(f"❌ 基础导入失败: {e}")
        return False


def test_graph_manager():
    """测试图管理器"""
    print("\n=== 测试图管理器 ===")
    
    try:
        from app.models.graph_manager import GraphManager, get_graph_manager
        print("✅ 图管理器导入成功")
        
        # 测试获取图管理器实例
        graph_manager = get_graph_manager()
        print(f"✅ 图管理器实例创建成功: {type(graph_manager).__name__}")
        
        return True
    except Exception as e:
        print(f"❌ 图管理器测试失败: {e}")
        return False


def test_model_factory():
    """测试模型工厂"""
    print("\n=== 测试模型工厂 ===")
    
    try:
        from app.models.factory import model_factory
        print("✅ 模型工厂导入成功")
        
        # 测试注册的模型
        registered_models = model_factory.list_models()
        print(f"✅ 已注册模型: {registered_models}")
        
        return True
    except Exception as e:
        print(f"❌ 模型工厂测试失败: {e}")
        return False


def test_type_safety():
    """测试类型安全"""
    print("\n=== 测试类型安全 ===")
    
    try:
        from app.models.graph import (
            BaseNode, BaseRelationship, 
            Node, Relationship, 
            FriendshipRelationship
        )
        
        # 创建测试实例
        node = Node()
        relationship = Relationship()
        friendship = FriendshipRelationship()
        
        # 测试类型检查
        print(f"  Node 实例是 BaseNode: {isinstance(node, BaseNode)}")
        print(f"  Relationship 实例是 BaseRelationship: {isinstance(relationship, BaseRelationship)}")
        print(f"  FriendshipRelationship 实例是 Relationship: {isinstance(friendship, Relationship)}")
        print(f"  FriendshipRelationship 实例是 BaseRelationship: {isinstance(friendship, BaseRelationship)}")
        
        return True
    except Exception as e:
        print(f"❌ 类型安全测试失败: {e}")
        return False


def test_relationship_types():
    """测试关系类型系统"""
    print("\n=== 测试关系类型系统 ===")
    
    try:
        from app.models.graph import (
            FriendshipRelationship, LocationRelationship, OwnershipRelationship
        )
        
        # 测试友谊关系
        friendship = FriendshipRelationship()
        friendship.friendship_level = "close"
        print(f"✅ 友谊关系创建成功，等级: {friendship.friendship_level}")
        
        # 测试位置关系
        location_rel = LocationRelationship()
        location_rel.location_type = "current"
        print(f"✅ 位置关系创建成功，类型: {location_rel.location_type}")
        
        # 测试所有权关系
        ownership_rel = OwnershipRelationship()
        ownership_rel.ownership_type = "owner"
        print(f"✅ 所有权关系创建成功，类型: {ownership_rel.ownership_type}")
        
        return True
    except Exception as e:
        print(f"❌ 关系类型测试失败: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("🚀 开始图模型系统测试\n")
    
    tests = [
        test_basic_imports,
        test_graph_manager,
        test_model_factory,
        test_type_safety,
        test_relationship_types
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
        print("🎉 所有测试通过！图模型系统工作正常。")
        return True
    else:
        print("⚠️  部分测试失败，请检查相关代码。")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
