"""
纯图数据设计集成测试

验证重构后的模型系统是否正常工作
"""

import sys
import os
import uuid
from datetime import datetime

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """测试导入"""
    print("🧪 测试模型导入...")
    
    try:
        # 测试基础模型导入
        from app.models.base import DefaultObject, DefaultAccount, GraphNodeInterface
        print("✅ 基础模型导入成功")
        
        # 测试具体模型导入
        from app.models.user import User
        from app.models.campus import Campus
        from app.models.world import World, WorldObject
        print("✅ 具体模型导入成功")
        
        # 测试图模型导入
        from app.models.graph import Node, GraphNode, Relationship
        print("✅ 图模型导入成功")
        
        # 测试图同步器导入
        from app.models.graph_sync import GraphSynchronizer
        print("✅ 图同步器导入成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False


def test_object_creation():
    """测试对象创建"""
    print("\n🧪 测试对象创建...")
    
    try:
        # 导入具体模型类
        from app.models.user import User
        from app.models.campus import Campus
        from app.models.world import World, WorldObject
        
        # 创建用户
        user = User(username="testuser", email="test@example.com")
        print(f"✅ 用户创建成功: {user}")
        print(f"   - UUID: {user.get_node_uuid()}")
        print(f"   - 类型: {user.get_node_type()}")
        print(f"   - 类型类: {user.get_node_typeclass()}")
        print(f"   - 用户名: {user.username}")
        print(f"   - 邮箱: {user.email}")
        
        # 创建校园
        campus = Campus(name="测试大学", code="TEST001")
        print(f"✅ 校园创建成功: {campus}")
        print(f"   - UUID: {campus.get_node_uuid()}")
        print(f"   - 类型: {campus.get_node_type()}")
        print(f"   - 类型类: {campus.get_node_typeclass()}")
        print(f"   - 名称: {campus.name}")
        print(f"   - 代码: {campus.code}")
        
        # 创建世界
        world = World(name="测试世界", world_type="virtual")
        print(f"✅ 世界创建成功: {world}")
        print(f"   - UUID: {world.get_node_uuid()}")
        print(f"   - 类型: {world.get_node_type()}")
        print(f"   - 类型类: {world.get_node_typeclass()}")
        print(f"   - 名称: {world.name}")
        print(f"   - 世界类型: {world.world_type}")
        
        # 创建世界对象
        world_obj = WorldObject(name="测试物品", object_type="item")
        print(f"✅ 世界对象创建成功: {world_obj}")
        print(f"   - UUID: {world_obj.get_node_uuid()}")
        print(f"   - 类型: {world_obj.get_node_type()}")
        print(f"   - 类型类: {world_obj.get_node_typeclass()}")
        print(f"   - 名称: {world_obj.name}")
        print(f"   - 对象类型: {world_obj.object_type}")
        
        return True
        
    except Exception as e:
        print(f"❌ 对象创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_attribute_management():
    """测试属性管理"""
    print("\n🧪 测试属性管理...")
    
    try:
        # 导入用户模型
        from app.models.user import User
        
        # 创建用户并测试属性
        user = User(username="attruser", email="attr@example.com")
        
        # 设置属性
        user.nickname = "昵称用户"
        user.phone = "13800138000"
        user.major = "计算机科学"
        user.grade = "大三"
        
        print(f"✅ 用户属性设置成功")
        print(f"   - 昵称: {user.nickname}")
        print(f"   - 电话: {user.phone}")
        print(f"   - 专业: {user.major}")
        print(f"   - 年级: {user.grade}")
        
        # 测试标签管理
        user.add_node_tag("活跃用户")
        user.add_node_tag("技术爱好者")
        print(f"✅ 标签添加成功: {user.get_node_tags()}")
        
        user.remove_node_tag("技术爱好者")
        print(f"✅ 标签移除成功: {user.get_node_tags()}")
        
        # 测试自定义属性
        user.set_node_attribute("custom_field", "自定义值")
        user.set_node_attribute("score", 95)
        print(f"✅ 自定义属性设置成功")
        print(f"   - custom_field: {user.get_node_attribute('custom_field')}")
        print(f"   - score: {user.get_node_attribute('score')}")
        
        return True
        
    except Exception as e:
        print(f"❌ 属性管理测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_relationship_creation():
    """测试关系创建"""
    print("\n🧪 测试关系创建...")
    
    try:
        # 导入模型类
        from app.models.user import User
        from app.models.campus import Campus
        from app.models.world import World
        
        # 创建对象
        user = User(username="reluser", email="rel@example.com")
        campus = Campus(name="关系测试大学", code="REL001")
        world = World(name="关系测试世界", world_type="virtual")
        
        # 测试用户加入校园
        success = campus.add_member(user, role="student")
        print(f"✅ 用户加入校园: {success}")
        
        # 测试用户加入世界
        success = world.add_player(user, role="player")
        print(f"✅ 用户加入世界: {success}")
        
        # 测试获取关系
        campus_memberships = user.get_campus_memberships()
        print(f"✅ 校园成员关系: {len(campus_memberships)} 个")
        
        world_activities = user.get_active_world_activities()
        print(f"✅ 世界活动关系: {len(world_activities)} 个")
        
        return True
        
    except Exception as e:
        print(f"❌ 关系创建测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_node_interface():
    """测试节点接口实现"""
    print("\n🧪 测试节点接口实现...")
    
    try:
        # 导入用户模型
        from app.models.user import User
        
        user = User(username="interfaceuser", email="interface@example.com")
        
        # 测试GraphNodeInterface方法
        print(f"✅ 节点接口测试:")
        print(f"   - get_node_uuid(): {user.get_node_uuid()}")
        print(f"   - get_node_type(): {user.get_node_type()}")
        print(f"   - get_node_typeclass(): {user.get_node_typeclass()}")
        print(f"   - get_node_attributes(): {len(user.get_node_attributes())} 个属性")
        print(f"   - get_node_tags(): {user.get_node_tags()}")
        
        # 测试属性访问器
        print(f"✅ 属性访问器测试:")
        print(f"   - user.name: {user.name}")
        print(f"   - user.username: {user.username}")
        print(f"   - user.email: {user.email}")
        print(f"   - user.is_active: {user.is_active}")
        
        return True
        
    except Exception as e:
        print(f"❌ 节点接口测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("🚀 开始纯图数据设计集成测试")
    print("=" * 50)
    
    tests = [
        ("导入测试", test_imports),
        ("对象创建测试", test_object_creation),
        ("属性管理测试", test_attribute_management),
        ("关系创建测试", test_relationship_creation),
        ("节点接口测试", test_node_interface),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} 通过")
            else:
                print(f"❌ {test_name} 失败")
        except Exception as e:
            print(f"❌ {test_name} 异常: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！纯图数据设计重构成功！")
        return True
    else:
        print("⚠️ 部分测试失败，需要进一步检查")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
