#!/usr/bin/env python3
"""
测试ORM重构后的功能

验证命令加载器使用ORM查询替代原始SQL的功能
包括性能对比和功能验证

作者：AI Assistant
创建时间：2025-08-24
"""

import sys
import os
import time
from datetime import datetime

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_orm_models():
    """测试ORM模型定义"""
    print("\n🧪 测试ORM模型定义")
    print("=" * 50)
    
    try:
        from app.models.graph import Node, Relationship, NodeType, RelationshipType
        
        print("✅ ORM模型导入成功")
        
        # 测试模型属性
        print("\n📋 测试模型属性")
        print("-" * 30)
        
        # Node模型
        print(f"  📊 Node模型:")
        print(f"     - 表名: {Node.__tablename__}")
        print(f"     - 列数: {len(Node.__table__.columns)}")
        print(f"     - 索引数: {len(Node.__table__.indexes)}")
        print(f"     - 关系数: {len(Node.__mapper__.relationships)}")
        
        # Relationship模型
        print(f"  📊 Relationship模型:")
        print(f"     - 表名: {Relationship.__tablename__}")
        print(f"     - 列数: {len(Relationship.__table__.columns)}")
        print(f"     - 索引数: {len(Relationship.__table__.indexes)}")
        print(f"     - 关系数: {len(Relationship.__mapper__.relationships)}")
        
        # NodeType模型
        print(f"  📊 NodeType模型:")
        print(f"     - 表名: {NodeType.__tablename__}")
        print(f"     - 列数: {len(NodeType.__table__.columns)}")
        print(f"     - 索引数: {len(NodeType.__table__.indexes)}")
        
        # RelationshipType模型
        print(f"  📊 RelationshipType模型:")
        print(f"     - 表名: {RelationshipType.__tablename__}")
        print(f"     - 列数: {len(RelationshipType.__table__.columns)}")
        print(f"     - 索引数: {len(RelationshipType.__table__.indexes)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试ORM模型定义失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_orm_query_methods():
    """测试ORM查询方法"""
    print("\n🧪 测试ORM查询方法")
    print("=" * 50)
    
    try:
        from app.models.graph import Node, Relationship, NodeType, RelationshipType
        from app.core.database import SessionLocal
        
        print("✅ ORM查询方法测试")
        
        session = SessionLocal()
        
        # 测试Node查询方法
        print("\n📋 测试Node查询方法")
        print("-" * 30)
        
        # 获取所有节点类型
        node_types = NodeType.get_active_types(session)
        print(f"  ✅ 活跃节点类型数量: {len(node_types)}")
        
        # 获取所有关系类型
        rel_types = RelationshipType.get_active_types(session)
        print(f"  ✅ 活跃关系类型数量: {len(rel_types)}")
        
        # 测试按类型获取节点
        command_nodes = Node.get_by_type(session, 'command')
        print(f"  ✅ 命令节点数量: {len(command_nodes)}")
        
        # 测试按类型获取关系
        contains_rels = Relationship.get_by_type(session, 'contains')
        print(f"  ✅ 包含关系数量: {len(contains_rels)}")
        
        # 测试搜索方法
        system_commands = Node.search_by_attribute(session, 'help_category', 'system', 'command')
        print(f"  ✅ 系统命令数量: {len(system_commands)}")
        
        session.close()
        
        return True
        
    except Exception as e:
        print(f"❌ 测试ORM查询方法失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_orm_loader_performance():
    """测试ORM加载器性能"""
    print("\n🧪 测试ORM加载器性能")
    print("=" * 50)
    
    try:
        from app.commands.loaders import command_loader, cmdset_loader
        
        print("✅ ORM加载器性能测试")
        
        # 测试命令配置加载性能
        print("\n📋 测试命令配置加载性能")
        print("-" * 30)
        
        # 测试单个命令加载
        start_time = time.time()
        look_config = command_loader.load_command_config('look', force_reload=True)
        single_load_time = time.time() - start_time
        
        if look_config:
            print(f"  ✅ 单个命令加载成功: {single_load_time:.4f}秒")
        else:
            print("  ❌ 单个命令加载失败")
            return False
        
        # 测试所有命令加载
        start_time = time.time()
        all_commands = command_loader.load_all_command_configs(force_reload=True)
        all_load_time = time.time() - start_time
        
        if all_commands:
            print(f"  ✅ 所有命令加载成功: {all_load_time:.4f}秒 ({len(all_commands)} 个命令)")
        else:
            print("  ❌ 所有命令加载失败")
            return False
        
        # 测试命令集合配置加载性能
        print("\n📋 测试命令集合配置加载性能")
        print("-" * 30)
        
        # 测试单个命令集合加载
        start_time = time.time()
        system_cmdset = cmdset_loader.load_cmdset_config('system_cmdset', force_reload=True)
        cmdset_load_time = time.time() - start_time
        
        if system_cmdset:
            print(f"  ✅ 命令集合加载成功: {cmdset_load_time:.4f}秒")
        else:
            print("  ❌ 命令集合加载失败")
            return False
        
        # 测试命令集合命令加载
        start_time = time.time()
        cmdset_commands = cmdset_loader.load_cmdset_commands('system_cmdset', force_reload=True)
        commands_load_time = time.time() - start_time
        
        if cmdset_commands:
            print(f"  ✅ 命令集合命令加载成功: {commands_load_time:.4f}秒 ({len(cmdset_commands)} 个命令)")
        else:
            print("  ❌ 命令集合命令加载失败")
            return False
        
        # 性能总结
        print("\n📋 性能总结")
        print("-" * 30)
        print(f"  📊 单个命令加载: {single_load_time:.4f}秒")
        print(f"  📊 所有命令加载: {all_load_time:.4f}秒")
        print(f"  📊 命令集合加载: {cmdset_load_time:.4f}秒")
        print(f"  📊 命令集合命令加载: {commands_load_time:.4f}秒")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试ORM加载器性能失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_orm_functionality():
    """测试ORM功能完整性"""
    print("\n🧪 测试ORM功能完整性")
    print("=" * 50)
    
    try:
        from app.commands.loaders import command_loader, cmdset_loader
        
        print("✅ ORM功能完整性测试")
        
        # 测试命令配置加载
        print("\n📋 测试命令配置加载")
        print("-" * 30)
        
        look_config = command_loader.load_command_config('look')
        if look_config:
            print(f"  ✅ look命令配置加载成功")
            print(f"     - 命令键: {look_config['key']}")
            print(f"     - 描述: {look_config['description'][:50]}...")
            print(f"     - 分类: {look_config['attributes'].get('help_category', 'unknown')}")
            print(f"     - 别名: {look_config['attributes'].get('command_aliases', [])}")
        else:
            print("  ❌ look命令配置加载失败")
            return False
        
        # 测试按分类加载命令
        system_commands = command_loader.load_commands_by_category('system')
        if system_commands:
            print(f"  ✅ 系统分类命令加载成功: {len(system_commands)} 个")
            for cmd_key in system_commands.keys():
                print(f"     - {cmd_key}")
        else:
            print("  ❌ 系统分类命令加载失败")
            return False
        
        # 测试命令集合配置加载
        print("\n📋 测试命令集合配置加载")
        print("-" * 30)
        
        system_cmdset = cmdset_loader.load_cmdset_config('system_cmdset')
        if system_cmdset:
            print(f"  ✅ system_cmdset配置加载成功")
            print(f"     - 集合键: {system_cmdset['key']}")
            print(f"     - 描述: {system_cmdset['description']}")
            print(f"     - 合并类型: {system_cmdset['attributes'].get('cmdset_mergetype', 'unknown')}")
            print(f"     - 优先级: {system_cmdset['attributes'].get('cmdset_priority', 'unknown')}")
        else:
            print("  ❌ system_cmdset配置加载失败")
            return False
        
        # 测试命令集合命令加载
        cmdset_commands = cmdset_loader.load_cmdset_commands('system_cmdset')
        if cmdset_commands:
            print(f"  ✅ system_cmdset命令加载成功: {len(cmdset_commands)} 个")
            for cmd_info in cmdset_commands[:3]:  # 只显示前3个
                print(f"     - {cmd_info['key']}: {cmd_info['attributes'].get('help_category', 'unknown')}")
        else:
            print("  ❌ system_cmdset命令加载失败")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 测试ORM功能完整性失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_tests():
    """运行所有测试"""
    print("🚀 开始测试ORM重构后的功能")
    print("=" * 60)
    
    test_functions = [
        ("ORM模型定义测试", test_orm_models),
        ("ORM查询方法测试", test_orm_query_methods),
        ("ORM加载器性能测试", test_orm_loader_performance),
        ("ORM功能完整性测试", test_orm_functionality)
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
        print("\n🎉 所有测试通过！ORM重构成功")
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
